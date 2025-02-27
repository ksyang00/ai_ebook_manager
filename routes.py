# routes.py
from flask import Flask, request, redirect, flash, render_template, session, jsonify, send_file, url_for, render_template_string
from datetime import datetime
from io import BytesIO
from werkzeug.datastructures import FileStorage
from models import db, User, Ebook, Metadata, Logging
from utils import (
    generate_summary, extract_text_from_pdf, extract_text_from_epub, extract_text,
    extract_text_from_docx, extract_text_from_txt, preprocess_text, generate_metadata
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:password@localhost/ebookdb'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB로 제한
db.init_app(app)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'GET':
        return render_template('upload.html')  # GET 요청 시 upload.html 렌더링
    elif request.method == 'POST':
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401

        try:
            ALLOWED_EXTENSIONS = {'pdf', 'epub', 'docx', 'txt'}  # 소문자로
            
            # 파일 및 폼 데이터 처리
            title = request.form.get('title')
            file = request.files.get('file')

            # 필수 필드 확인
            if not title or not file:
                return jsonify({'success': False, 'message': 'Title and file are required'}), 400

            # 파일 형식 확인
            file_format = file.filename.split('.')[-1]
            if file_format not in ALLOWED_EXTENSIONS:
                return jsonify({'success': False, 'message': 'Unsupported file format'}), 400

            # 파일에서 텍스트 추출
            file_data = file.read()
            file.seek(0)  # 파일 포인터를 처음으로 되돌림
            text = extract_text(file, file_format)

            # # 요약 생성 (언어 감지 후 동일한 언어로 요약)
            summary = request.form.get('summary')
            # if not summary:
            #     summary = generate_summary(text)

            # publish_date가 제공되지 않았을 경우 현재 날짜로 설정
            publish_date = request.form.get('publish_date')
            if not publish_date:
                publish_date = datetime.utcnow().date()
            else:
                publish_date = datetime.strptime(publish_date, '%Y-%m-%d').date()

            # 새 전자책 생성
            new_ebook = Ebook(
                title=title,
                author=request.form.get('author'),
                isbn=request.form.get('isbn'),
                publish_date=publish_date,
                file_format=file_format,
                file_data=file_data,
                summary=summary,
                user_id=session['user_id'],
                created_date=datetime.utcnow()
            )

            # 메타데이터 생성 (TF-IDF 사용)
            metadata = generate_metadata(text)
            for meta in metadata:
                new_meta = Metadata(tag=meta['tag'], value=meta['value'], ebook=new_ebook)
                db.session.add(new_meta)

            db.session.add(new_ebook)
            db.session.commit()

            return jsonify({'success': True, 'redirect_url': url_for('list_ebooks')}), 200  # 리디렉션 URL 추가
        
        except FileNotFoundError:
            return jsonify({'success': False, 'message': 'File not found'}), 400
        except TypeError as e:
            return jsonify({'success': False, 'message': f"Type Error: {str(e)}"}), 500
        except Exception as e:
            db.session.rollback()
            print(f"An error occurred: {e}")  # 또는 로깅
            return jsonify({'success': False, 'message': f"An unexpected error: {str(e)}"}), 500

 
@app.route('/generate_summary', methods=['POST'])
def generate_summary_api():
    data = request.get_json()
    ebook_id = data.get('ebook_id')

    if not ebook_id:
        return jsonify({"success": False, "message": "ebook_id is required"}), 400

    try:
        # 데이터베이스에서 책 찾기
        ebook = Ebook.query.get(ebook_id)
        if not ebook:
            return jsonify({"success": False, "message": "Ebook not found"}), 404

        # 책 파일에서 텍스트 추출
        file_format = ebook.file_format
        file_stream = BytesIO(ebook.file_data)
        file = FileStorage(
            stream=file_stream,
            filename=f"{ebook.title}.{ebook.file_format}",
            content_type=f"application/{ebook.file_format}"
        )
        
        # 책 파일에서 text 추출
        text = extract_text(file, file_format)

        # 요약 생성
        summary = generate_summary(text)  # 요약 생성 함수 호출

        return jsonify({"success": True, "summary": summary})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# 로그인 페이지
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['grade'] = user.grade  # 사용자 등급 저장
            return redirect(url_for('list_ebooks'))
        
        session.pop('user_id', None)
        session.pop('username', None)
        session.pop('grade', None)
        flash('Invalid username or password')
    return render_template('login.html')

# 사용자 등록 페이지
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        # 비밀번호 해시
        new_user = User(
            username=username,
            email=email
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        flash('User registered successfully')
        return redirect(url_for('login'))
    return render_template('register.html')

# 전자책 목록 페이지
@app.route('/list')
def list_ebooks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # 현재 로그인한 사용자의 ID
    current_user_id = session['user_id']
    
    # 현재 로그인한 사용자가 업로드한 책만 가져오기
    ebooks = db.session.query(Ebook, User.username)\
                      .join(User, Ebook.user_id == User.id)\
                      .filter(Ebook.user_id == current_user_id)\
                      .all()
    
    return render_template('list.html', ebooks=ebooks, current_user_id=current_user_id)

# 전자책 상세 페이지
@app.route('/detail/<int:ebook_id>')
def detail(ebook_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    ebook = Ebook.query.get_or_404(ebook_id)
    
    # 현재 로그인한 사용자가 업로드한 책인지 확인
    if ebook.user_id != session['user_id'] and session.get('user_id') != 1:
        flash('You do not have permission to view this ebook')
        return redirect(url_for('list_ebooks'))

    return render_template('detail.html', ebook=ebook)

# 전자책 수정 페이지
@app.route('/edit/<int:ebook_id>', methods=['GET', 'POST'])
def edit_ebook(ebook_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    ebook = Ebook.query.get_or_404(ebook_id)
    
    # 현재 로그인한 사용자가 업로드한 책인지 확인
    if ebook.user_id != session['user_id'] and session.get('user_id') != 1:
        flash('You do not have permission to edit this ebook')
        return redirect(url_for('list_ebooks'))
    
    if request.method == 'POST':
        # 전자책 정보 업데이트
        ebook.title = request.form['title']
        ebook.author = request.form['author']
        ebook.isbn = request.form['isbn']
        ebook.publish_date = datetime.strptime(request.form['publish_date'], '%Y-%m-%d')
        ebook.summary = request.form['summary']
        ebook.updated_date = datetime.utcnow()  # 현재 시간으로 업데이트

        # 기존 메타데이터 업데이트
        for meta in ebook.ebook_metadata:  # Changed from 'metadata' to 'ebook_metadata'
            meta.tag = request.form.get(f'meta_tag_{meta.id}')
            meta.value = request.form.get(f'meta_value_{meta.id}')

        # 새로운 메타데이터 추가
        new_tags = request.form.getlist('meta_tag_new[]')
        new_values = request.form.getlist('meta_value_new[]')
        for tag, value in zip(new_tags, new_values):
            if tag and value:  # 태그와 값이 모두 있는 경우에만 추가
                new_meta = Metadata(tag=tag, value=value, ebook_id=ebook.id)
                db.session.add(new_meta)

        db.session.commit()
        flash('Ebook updated successfully')
        return redirect(url_for('list_ebooks'))
    
    return render_template('edit_ebook.html', ebook=ebook)

# 전자책 삭제
@app.route('/delete/<int:ebook_id>')
def delete_ebook(ebook_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    ebook = Ebook.query.get_or_404(ebook_id)
    
    # 현재 로그인한 사용자가 업로드한 책인지 확인
    if ebook.user_id != session['user_id'] and session.get('user_id') != 1:
        flash('You do not have permission to delete this ebook')
        return redirect(url_for('list_ebooks'))
    
    # 전자책에 연결된 메타데이터 삭제
    Metadata.query.filter_by(ebook_id=ebook.id).delete()
    
    # 전자책 삭제
    db.session.delete(ebook)
    db.session.commit()
    flash('Ebook and associated metadata deleted successfully')
    return redirect(url_for('list_ebooks'))

# 전자책 다운로드
@app.route('/download/<int:ebook_id>')
def download(ebook_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    ebook = Ebook.query.get_or_404(ebook_id)
    
    # 현재 로그인한 사용자가 업로드한 책인지 또는 관리자인지 확인
    if ebook.user_id != session['user_id'] and session.get('user_id') != 1:
        flash('You do not have permission to download this ebook')
        return redirect(url_for('list_ebooks'))
    
    # 파일 다운로드
    return send_file(
        BytesIO(ebook.file_data),
        download_name=f"{ebook.title}.{ebook.file_format}",
        as_attachment=True
    )

# 사용자 관리 페이지
@app.route('/manage_users')
def manage_users():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # 관리자 권한 확인 (예: user_id가 1인 경우 관리자로 간주)
    if session.get('user_id') != 1:
        flash('You do not have permission to access this page')
        return redirect(url_for('list_ebooks'))
    
    # 모든 사용자 목록 가져오기
    users = User.query.all()
    return render_template('manage_users.html', users=users)

# 사용자 수정 페이지
@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # 관리자 권한 확인 (예: user_id가 1인 경우 관리자로 간주)
    if session.get('user_id') != 1:
        flash('You do not have permission to access this page')
        return redirect(url_for('list_ebooks'))
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.username = request.form['username']
        user.email = request.form['email']
        user.grade = request.form['grade']
        db.session.commit()
        flash('User updated successfully')
        return redirect(url_for('manage_users'))
    
    return render_template('edit_user.html', user=user)

# 사용자 삭제
@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # 관리자 권한 확인 (예: user_id가 1인 경우 관리자로 간주)
    if session.get('user_id') != 1:
        flash('You do not have permission to delete this user')
        return redirect(url_for('list_ebooks'))
    
    user = User.query.get_or_404(user_id)
    
    # 현재 로그인한 사용자가 자신을 삭제하지 못하도록 방지
    if user.id == session['user_id']:
        flash('You cannot delete yourself')
        return redirect(url_for('manage_users'))
    
    # 사용자가 등록한 모든 전자책과 메타데이터 삭제
    ebooks = Ebook.query.filter_by(user_id=user.id).all()
    for ebook in ebooks:
        # 전자책에 연결된 메타데이터 삭제
        Metadata.query.filter_by(ebook_id=ebook.id).delete()
        # 전자책 삭제
        db.session.delete(ebook)
    
    # 사용자 삭제
    db.session.delete(user)
    db.session.commit()
    flash('User and associated ebooks/metadata deleted successfully')
    return redirect(url_for('manage_users'))

@app.route('/ebook_all')
def list_all_ebooks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # 관리자 권한 확인
    if session.get('user_id') != 1:
        flash('You do not have permission to access this page')
        return redirect(url_for('list_ebooks'))
    
    # 모든 사용자의 책 가져오기
    ebooks = db.session.query(Ebook, User.username)\
                      .join(User, Ebook.user_id == User.id)\
                      .all()
    
    return render_template('ebook_all.html', ebooks=ebooks)

# 로그 조회 라우트
@app.route('/logs')
def view_logs():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('user_id') != 1:
        flash('You do not have permission to view logs')
        return redirect(url_for('list_ebooks'))
    
    logs = Logging.query.order_by(Logging.id.desc()).all()
    return render_template('logs.html', logs=logs)

# 로그아웃
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('grade', None)
    flash('You have been logged out')
    return redirect(url_for('login'))