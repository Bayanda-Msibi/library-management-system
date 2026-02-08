# models.py
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f"<Person {self.name}>"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')  # 'admin' or 'user'

    borrows = db.relationship('Borrow', backref='user', lazy=True)

    def __repr__(self):
        return f"<User {self.username} role={self.role}>"

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    books = db.relationship('Book', backref='category', lazy=True)

    def __repr__(self):
        return f"<Category {self.name}>"

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)

    borrows = db.relationship('Borrow', backref='book', lazy=True)

    def __repr__(self):
        return f"<Book {self.title} by {self.author}>"

class Borrow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    borrow_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(days=14))
    return_date = db.Column(db.DateTime, nullable=True)

    def is_overdue(self) -> bool:
        return self.return_date is None and datetime.utcnow() > self.due_date

    def days_overdue(self) -> int:
        if not self.is_overdue():
            return 0
        return (datetime.utcnow().date() - self.due_date.date()).days

    def __repr__(self):
        status = 'returned' if self.return_date else 'out'
        return f"<Borrow user={self.user_id} book={self.book_id} {status}>"
