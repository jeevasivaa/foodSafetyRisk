from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
from utils.helpers import save_upload, allowed_file

community_bp = Blueprint('community', __name__)
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'foodquality.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@community_bp.route('/')
def feed():
    sort = request.args.get('sort', 'hot')
    conn = get_db_connection()
    
    query = """
        SELECT p.*, u.name as author_name, 
               (SELECT COALESCE(SUM(vote_value), 0) FROM votes WHERE target_type='post' AND target_id=p.id) as score,
               (SELECT COUNT(*) FROM comments WHERE post_id=p.id) as comment_count
        FROM posts p
        JOIN users u ON p.user_id = u.id
    """
    
    if sort == 'new':
        query += " ORDER BY p.created_at DESC"
    else:
        query += " ORDER BY score DESC, p.created_at DESC"
        
    posts = conn.execute(query).fetchall()
    
    # Get user's votes if logged in
    user_votes = {}
    if 'user_id' in session:
        votes = conn.execute("SELECT target_id, vote_value FROM votes WHERE target_type='post' AND user_id=?", (session['user_id'],)).fetchall()
        user_votes = {v['target_id']: v['vote_value'] for v in votes}
        
    conn.close()
    return render_template('community/feed.html', posts=posts, sort=sort, user_votes=user_votes)

@community_bp.route('/new', methods=['GET', 'POST'])
def create_post():
    if 'user_id' not in session:
        flash("Please log in to post.", "warning")
        return redirect(url_for('auth.login'))
        
    scan_id = request.args.get('scan_id')
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category = request.form['category']
        scan_id_val = request.form.get('scan_id') or None
        
        
        img_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                img_filename = save_upload(file, "community")
                
        conn = get_db_connection()
        conn.execute("INSERT INTO posts (user_id, title, content, scan_id, category, image) VALUES (?, ?, ?, ?, ?, ?)",
                     (session['user_id'], title, content, scan_id_val, category, img_filename))
        conn.commit()
        conn.close()
        flash("Post created successfully!", "success")
        return redirect(url_for('community.feed'))
        
    scan = None
    if scan_id:
        conn = get_db_connection()
        scan = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
        conn.close()
        
    return render_template('community/create_post.html', scan=scan)

@community_bp.route('/post/<int:post_id>')
def view_post(post_id):
    conn = get_db_connection()
    post = conn.execute("""
        SELECT p.*, u.name as author_name,
               (SELECT COALESCE(SUM(vote_value), 0) FROM votes WHERE target_type='post' AND target_id=p.id) as score
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.id = ?
    """, (post_id,)).fetchone()
    
    if not post:
        conn.close()
        flash("Post not found.", "danger")
        return redirect(url_for('community.feed'))
        
    comments_raw = conn.execute("""
        SELECT c.*, u.name as author_name,
               (SELECT COALESCE(SUM(vote_value), 0) FROM votes WHERE target_type='comment' AND target_id=c.id) as score
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.post_id = ?
        ORDER BY c.created_at ASC
    """, (post_id,)).fetchall()
    
    # Organize into a tree
    comments = []
    replies_map = {}
    
    # Convert Row objects to dicts
    for c in comments_raw:
        c_dict = dict(c)
        c_dict['replies'] = []
        if c_dict.get('parent_id'):
            if c_dict['parent_id'] not in replies_map:
                replies_map[c_dict['parent_id']] = []
            replies_map[c_dict['parent_id']].append(c_dict)
        else:
            comments.append(c_dict)
            
    # Attach replies recursively
    def attach_replies(node):
        if node['id'] in replies_map:
            node['replies'] = replies_map[node['id']]
            for r in node['replies']:
                attach_replies(r)
                
    for c in comments:
        attach_replies(c)
        
    # Sort top-level comments by score descending
    comments.sort(key=lambda x: x['score'], reverse=True)
    
    scan = None
    if post['scan_id']:
        scan = conn.execute("SELECT * FROM scans WHERE id = ?", (post['scan_id'],)).fetchone()
        
    user_vote = 0
    if 'user_id' in session:
        v = conn.execute("SELECT vote_value FROM votes WHERE target_type='post' AND target_id=? AND user_id=?", (post_id, session['user_id'])).fetchone()
        if v:
            user_vote = v['vote_value']
            
    conn.close()
    return render_template('community/view_post.html', post=post, comments=comments, scan=scan, user_vote=user_vote)

@community_bp.route('/post/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        flash("Please log in to comment.", "warning")
        return redirect(url_for('auth.login'))
        
    content = request.form['content']
    parent_id = request.form.get('parent_id') or None
    img_filename = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename and allowed_file(file.filename):
            img_filename = save_upload(file, "community")
            
    conn = get_db_connection()
    conn.execute("INSERT INTO comments (post_id, user_id, content, image, parent_id) VALUES (?, ?, ?, ?, ?)",
                 (post_id, session['user_id'], content, img_filename, parent_id))
    conn.commit()
    conn.close()
    flash("Comment added!", "success")
    return redirect(url_for('community.view_post', post_id=post_id))

@community_bp.route('/vote', methods=['POST'])
def vote():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    target_type = data.get('target_type') # 'post' or 'comment'
    target_id = data.get('target_id')
    vote_value = int(data.get('vote_value')) # 1 or -1
    
    if target_type not in ['post', 'comment'] or vote_value not in [1, -1, 0]:
        return jsonify({"error": "Invalid input"}), 400
        
    conn = get_db_connection()
    
    # Check existing vote
    existing = conn.execute("SELECT * FROM votes WHERE user_id=? AND target_type=? AND target_id=?", 
                            (session['user_id'], target_type, target_id)).fetchone()
                            
    if existing:
        if vote_value == 0 or existing['vote_value'] == vote_value:
            # Toggle off
            conn.execute("DELETE FROM votes WHERE user_id=? AND target_type=? AND target_id=?",
                         (session['user_id'], target_type, target_id))
        else:
            # Update vote
            conn.execute("UPDATE votes SET vote_value=? WHERE user_id=? AND target_type=? AND target_id=?",
                         (vote_value, session['user_id'], target_type, target_id))
    else:
        if vote_value != 0:
            conn.execute("INSERT INTO votes (user_id, target_type, target_id, vote_value) VALUES (?, ?, ?, ?)",
                         (session['user_id'], target_type, target_id, vote_value))
                     
    conn.commit()
    
    # Get new score
    score = conn.execute("SELECT COALESCE(SUM(vote_value), 0) as score FROM votes WHERE target_type=? AND target_id=?", 
                         (target_type, target_id)).fetchone()['score']
    conn.close()
    
    return jsonify({"success": True, "new_score": score})

@community_bp.route('/post/<int:post_id>/delete', methods=['POST'])
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    conn = get_db_connection()
    post = conn.execute("SELECT user_id FROM posts WHERE id = ?", (post_id,)).fetchone()
    
    if post and (post['user_id'] == session['user_id'] or session.get('role') == 'admin'):
        conn.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
        conn.execute("DELETE FROM votes WHERE target_type = 'post' AND target_id = ?", (post_id,))
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        conn.commit()
        flash("Post deleted successfully.", "success")
    else:
        flash("Unauthorized action.", "danger")
        
    conn.close()
    return redirect(url_for('community.feed'))

@community_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    conn = get_db_connection()
    comment = conn.execute("SELECT user_id, post_id FROM comments WHERE id = ?", (comment_id,)).fetchone()
    
    if comment and (comment['user_id'] == session['user_id'] or session.get('role') == 'admin'):
        post_id = comment['post_id']
        conn.execute("DELETE FROM votes WHERE target_type = 'comment' AND target_id = ?", (comment_id,))
        conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
        conn.commit()
        flash("Comment deleted.", "success")
    else:
        post_id = None
        flash("Unauthorized action.", "danger")
        
    conn.close()
    if post_id:
        return redirect(url_for('community.view_post', post_id=post_id))
    return redirect(url_for('community.feed'))
