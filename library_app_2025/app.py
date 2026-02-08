# app.py
from datetime import datetime
from io import BytesIO

from flask import (
    Flask, flash, render_template, request, redirect, url_for, Response, send_file, abort
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_

from models import db, Person, User, Book, Category, Borrow
from helpers import admin_required

# Optional PDF export (reportlab)
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.config['SECRET_KEY'] = 'spiderman_123'  # change in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Ensure DB + initial admin user exist
def create_tables_and_admin():
    db.create_all()
    # create an admin user automatically if none exists
    admin_user = User.query.filter_by(role='admin').first()
    if not admin_user:
        # change 'admin'/'admin123' to secure values for your environment
        if not User.query.filter_by(username='administrator').first():
            hashed = generate_password_hash('administrator123', method='pbkdf2:sha256', salt_length=20)
            u = User(username='administrator', password=hashed, role='admin')
            db.session.add(u)
            db.session.commit()
            app.logger.info("Created default admin user 'administrator' with password 'administrator123'")

# ---------------------
# Authentication
# ---------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'warning')
            return redirect(url_for('register'))

        hashed = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
        new_user = User(username=username, password=hashed, role='user')
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful — please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('index'))
        flash('Invalid credentials.', 'danger')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
#@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# ---------------------
# Home
# ---------------------
@app.route('/')
#@login_required
def index():
    return render_template('index.html')

# ---------------------
# Person demo (existing feature)
# ---------------------
@app.route('/greet', methods=['POST'])
#@login_required
def greet():
    name = request.form['name'].strip()
    if not name:
        flash('Name cannot be empty.', 'warning')
        return redirect(url_for('index'))
    db.session.add(Person(name=name))
    db.session.commit()
    return render_template('greet.html', name=name)

@app.route('/names')
@login_required
def list_names():
    people = Person.query.order_by(Person.id.desc()).all()
    return render_template('names.html', people=people)

@app.route('/delete/<int:id>', methods=['POST'])
#@login_required
def delete_name(id):
    person = Person.query.get_or_404(id)
    db.session.delete(person)
    db.session.commit()
    flash('Name deleted.', 'info')
    return redirect(url_for('list_names'))

@app.route('/edit/<int:id>')
@login_required
def edit_name(id):
    person = Person.query.get_or_404(id)
    return render_template('edit.html', person=person)

@app.route('/update/<int:id>', methods=['POST'])
#@login_required
def update_name(id):
    person = Person.query.get_or_404(id)
    new_name = request.form['name'].strip()
    if not new_name:
        flash('Name cannot be empty.', 'warning')
        return redirect(url_for('edit_name', id=id))
    person.name = new_name
    db.session.commit()
    flash('Name updated!', 'success')
    return redirect(url_for('list_names'))

# ---------------------
# Categories (admin only for add/edit/delete)
# ---------------------
@app.route('/categories')
#@login_required
def view_categories():
    categories = Category.query.order_by(Category.name.asc()).all()
    return render_template('categories.html', categories=categories)

@app.route('/categories/add', methods=['GET', 'POST'])
#@admin_required
def add_category():
    if request.method == 'POST':
        name = request.form['name'].strip()
        if not name:
            flash('Category name cannot be empty.', 'warning')
            return redirect(url_for('add_category'))
        if Category.query.filter_by(name=name).first():
            flash('Category already exists.', 'warning')
            return redirect(url_for('add_category'))
        db.session.add(Category(name=name))
        db.session.commit()
        flash('Category added.', 'success')
        return redirect(url_for('view_categories'))
    return render_template('add_category.html')

@app.route('/categories/edit/<int:cat_id>', methods=['GET', 'POST'])
#@admin_required
def edit_category(cat_id):
    category = Category.query.get_or_404(cat_id)
    if request.method == 'POST':
        new_name = request.form['name'].strip()
        if not new_name:
            flash('Category name cannot be empty.', 'warning')
            return redirect(url_for('edit_category', cat_id=cat_id))
        existing = Category.query.filter_by(name=new_name).first()
        if existing and existing.id != cat_id:
            flash('Category name already taken.', 'warning')
            return redirect(url_for('edit_category', cat_id=cat_id))
        category.name = new_name
        db.session.commit()
        flash('Category updated.', 'success')
        return redirect(url_for('view_categories'))
    return render_template('edit_category.html', category=category)

@app.route('/categories/delete/<int:cat_id>', methods=['POST'])
#@admin_required
def delete_category(cat_id):
    category = Category.query.get_or_404(cat_id)
    if category.books:
        flash('Cannot delete category assigned to books.', 'danger')
        return redirect(url_for('view_categories'))
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted.', 'info')
    return redirect(url_for('view_categories'))

# ---------------------
# Books (admin only for add/edit/delete; everyone can view)
# ---------------------
@app.route('/books')
#@login_required
def view_books():
    search_query = request.args.get('search', '').strip()
    filter_by = request.args.get('filter')
    category_id = request.args.get('category_id')

    q = Book.query

    if search_query:
        pattern = f"%{search_query}%"
        q = q.filter(or_(Book.title.ilike(pattern), Book.author.ilike(pattern)))

    if filter_by == 'available':
        q = q.filter(Book.quantity > 0)

    if category_id:
        try:
            cid = int(category_id)
            q = q.filter(Book.category_id == cid)
        except ValueError:
            pass

    books = q.order_by(Book.title.asc()).all()
    categories = Category.query.order_by(Category.name.asc()).all()

    return render_template(
        'books.html',
        books=books,
        search_query=search_query,
        filter_by=filter_by,
        categories=categories,
        selected_category_id=category_id,
        now=datetime.utcnow()
    )

@app.route('/books/add', methods=['GET', 'POST'])
#@admin_required
def add_book():
    categories = Category.query.order_by(Category.name.asc()).all()
    if request.method == 'POST':
        title = request.form['title'].strip()
        author = request.form['author'].strip()
        quantity = request.form.get('quantity', '0')
        category_id = request.form.get('category') or None

        if not title or not author:
            flash('Title and author required.', 'warning')
            return redirect(url_for('add_book'))

        try:
            qty = max(0, int(quantity))
        except ValueError:
            qty = 0

        book = Book(title=title, author=author, quantity=qty, category_id=category_id)
        db.session.add(book)
        db.session.commit()
        flash('Book added.', 'success')
        return redirect(url_for('view_books'))
    return render_template('add_book.html', categories=categories)

@app.route('/books/edit/<int:book_id>', methods=['GET', 'POST'])
#@admin_required
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)
    categories = Category.query.order_by(Category.name.asc()).all()
    if request.method == 'POST':
        book.title = request.form['title'].strip()
        book.author = request.form['author'].strip()
        try:
            book.quantity = max(0, int(request.form['quantity']))
        except ValueError:
            book.quantity = 0
        book.category_id = request.form.get('category') or None
        db.session.commit()
        flash('Book updated.', 'success')
        return redirect(url_for('view_books'))
    return render_template('edit_book.html', book=book, categories=categories)

@app.route('/books/delete/<int:book_id>', methods=['POST'])
#@admin_required
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    db.session.delete(book)
    db.session.commit()
    flash('Book deleted.', 'info')
    return redirect(url_for('view_books'))



# ---------------------
# CSV / PDF exports (any logged-in user)
# ---------------------
@app.route('/books/export/csv')
#@login_required
def export_books_csv():
    books = Book.query.order_by(Book.title.asc()).all()
    def generate():
        yield 'ID,Title,Author,Quantity,Category\n'
        for b in books:
            category_name = (b.category.name if b.category else '').replace(',', ' ')
            title = b.title.replace(',', ' ')
            author = b.author.replace(',', ' ')
            yield f'{b.id},{title},{author},{b.quantity},{category_name}\n'
    headers = {"Content-Disposition": "attachment; filename=books.csv"}
    return Response(generate(), mimetype='text/csv', headers=headers)

@app.route('/books/export/pdf')
#@login_required
def export_books_pdf():
    books = Book.query.order_by(Book.title.asc()).all()
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 40
    p.setFont("Helvetica-Bold", 16)
    p.drawString(40, y, "Book Inventory")
    y -= 30
    p.setFont("Helvetica", 11)
    for b in books:
        if y < 60:
            p.showPage()
            y = height - 40
            p.setFont("Helvetica", 11)
        category_name = b.category.name if b.category else '—'
        line = f"{b.id}. {b.title} — {b.author} | Qty: {b.quantity} | {category_name}"
        p.drawString(40, y, line)
        y -= 18
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='books.pdf', mimetype='application/pdf')

# ---------------------
# Borrow / Return (all users)
# ---------------------
@app.route('/borrow/<int:book_id>')
#@login_required
def borrow_book(book_id):
    book = Book.query.get_or_404(book_id)
    if book.quantity <= 0:
        flash('This book is out of stock.', 'warning')
        return redirect(url_for('view_books'))

    existing = Borrow.query.filter_by(user_id=current_user.id, book_id=book_id, return_date=None).first()
    if existing:
        flash('You already borrowed this title.', 'info')
        return redirect(url_for('view_books'))

    borrow = Borrow(user_id=current_user.id, book_id=book_id, borrow_date=datetime.utcnow())
    book.quantity -= 1
    db.session.add(borrow)
    db.session.commit()
    flash('Book borrowed! Due in 14 days.', 'success')
    return redirect(url_for('my_borrows'))

@app.route('/returns/<int:borrow_id>')
#@login_required
def return_book(borrow_id):
    borrow = Borrow.query.get_or_404(borrow_id)
    if borrow.user_id != current_user.id:
        flash("You can't return a book you didn't borrow.", 'danger')
        return redirect(url_for('view_books'))
    if borrow.return_date:
        flash('Already returned.', 'info')
        return redirect(url_for('my_borrows'))
    borrow.return_date = datetime.utcnow()
    borrow.book.quantity += 1
    db.session.commit()
    flash('Book returned. Thanks!', 'success')
    return redirect(url_for('my_borrows'))

@app.route('/my-borrows')
#@login_required
def my_borrows():
    borrows = Borrow.query.filter_by(user_id=current_user.id).order_by(Borrow.borrow_date.desc()).all()
    return render_template('my_borrows.html', borrows=borrows, now=datetime.utcnow())

# ---------------------
# Start
# ---------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
