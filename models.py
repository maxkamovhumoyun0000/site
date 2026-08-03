from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, Date, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    login_id = Column(String(30), unique=True, nullable=False, index=True)
    password = Column(String(64), nullable=False)
    password_used = Column(Boolean, default=False, nullable=False)
    first_name = Column(String(80), nullable=False)
    last_name = Column(String(80), nullable=False)
    phone = Column(String(20), nullable=True)
    subject = Column(String(20), nullable=False)
    telegram_id = Column(String(30), nullable=True, unique=True)
    login_type = Column(Integer, nullable=False, default=1)
    level = Column(String(40), nullable=True)
    access_enabled = Column(Boolean, default=False, nullable=False)
    group_id = Column(Integer, ForeignKey('groups.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    failed_logins = Column(Integer, default=0, nullable=False)
    blocked = Column(Boolean, default=False, nullable=False)

    test_results = relationship('TestResult', back_populates='user', cascade='all, delete-orphan')
    attendance = relationship('Attendance', back_populates='user', cascade='all, delete-orphan')
    group = relationship('Group', back_populates='users')


class Test(Base):
    __tablename__ = 'tests'

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(30), nullable=False)
    question = Column(Text, nullable=False)
    option_a = Column(String(255), nullable=False)
    option_b = Column(String(255), nullable=False)
    option_c = Column(String(255), nullable=False)
    option_d = Column(String(255), nullable=False)
    correct_option = Column(String(1), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TestResult(Base):
    __tablename__ = 'test_results'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    subject = Column(String(30), nullable=False)
    score = Column(Integer, nullable=False)
    max_score = Column(Integer, default=100)
    level = Column(String(64), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship('User', back_populates='test_results')


class Group(Base):
    __tablename__ = 'groups'

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    teacher_id = Column(BigInteger, ForeignKey('users.id'), nullable=True)
    level = Column(String(40), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship('User', back_populates='group')
    attendance = relationship('Attendance', back_populates='group', cascade='all, delete-orphan')


class Attendance(Base):
    __tablename__ = 'attendance'

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    group_id = Column(BigInteger, ForeignKey('groups.id', ondelete='CASCADE'), nullable=False)
    date = Column(Date, nullable=False)  # YYYY-MM-DD format
    status = Column(String(20), default='Absent', nullable=False)  # Present/Absent
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship('User', back_populates='attendance')
    group = relationship('Group', back_populates='attendance')


class Word(Base):
    __tablename__ = 'words'

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(255), nullable=False, index=True)
    subject = Column(String(40), nullable=False)
    language = Column(String(8), nullable=False)  # language of the word itself: 'en' or 'ru'
    level = Column(String(40), nullable=True)
    translation_uz = Column(String(255), nullable=True)
    translation_ru = Column(String(255), nullable=True)
    definition = Column(Text, nullable=True)
    example = Column(Text, nullable=True)
    added_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    added_by_user = relationship('User')


class VocabularyImport(Base):
    __tablename__ = 'vocabulary_imports'

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String(255), nullable=False)
    added_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    subject = Column(String(40), nullable=False)
    language = Column(String(8), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StudentPreference(Base):
    __tablename__ = 'student_preferences'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    preferred_translation = Column(String(8), nullable=True)  # 'uz' or 'ru'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship('User')

class Video(Base):
    __tablename__ = 'videos'
    id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    author = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    level = Column(String(40), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    video_url = Column(String(500), nullable=True)
    duration = Column(Integer, default=0)
    is_published = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class VideoProgress(Base):
    __tablename__ = 'video_progress'
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    video_id = Column(BigInteger, ForeignKey('videos.id', ondelete='CASCADE'), nullable=False)
    watched_seconds = Column(Integer, default=0)
    completed = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Book(Base):
    __tablename__ = 'books'
    id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    short_description = Column(Text, nullable=True)
    author = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    level = Column(String(40), nullable=True)
    cover_url = Column(String(500), nullable=True)
    pdf_url = Column(String(500), nullable=True)
    price = Column(Float, default=0.0)
    deadline_days = Column(Integer, default=0)
    is_published = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class BookQuestion(Base):
    __tablename__ = 'book_questions'
    id = Column(BigInteger, primary_key=True, index=True)
    book_id = Column(BigInteger, ForeignKey('books.id', ondelete='CASCADE'), nullable=False)
    question = Column(Text, nullable=False)
    option_a = Column(String(255), nullable=False)
    option_b = Column(String(255), nullable=False)
    option_c = Column(String(255), nullable=False)
    option_d = Column(String(255), nullable=False)
    correct_option = Column(String(1), nullable=False)
    explanation = Column(Text, nullable=True)
    question_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class StudentBookPurchase(Base):
    __tablename__ = 'student_book_purchases'
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    book_id = Column(BigInteger, ForeignKey('books.id', ondelete='CASCADE'), nullable=False)
    purchased_at = Column(DateTime(timezone=True), server_default=func.now())
    deadline_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), default='active')
