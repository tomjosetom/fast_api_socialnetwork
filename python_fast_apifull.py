from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from datetime import datetime
import databases
import sqlalchemy
import logging
from logging.handlers import RotatingFileHandler
import sys
from fastapi.responses import JSONResponse
from pydantic import BaseModel 

# Create logger
logger = logging.getLogger("blog_api")
logger.setLevel(logging.INFO)

# Create formatters
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Create handlers
file_handler = RotatingFileHandler("blog_api.log", maxBytes=10000, backupCount=3)
file_handler.setFormatter(file_formatter)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(console_formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Database setup
DATABASE_URL = "sqlite:///./test.db"
database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

# Define tables
users = sqlalchemy.Table(
    "users",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("username", sqlalchemy.String, unique=True, index=True),
    sqlalchemy.Column("hashed_password", sqlalchemy.String),
)

posts = sqlalchemy.Table(
    "posts",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("title", sqlalchemy.String),
    sqlalchemy.Column("content", sqlalchemy.String),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
)

comments = sqlalchemy.Table(
    "comments",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("content", sqlalchemy.String),
    sqlalchemy.Column("post_id", sqlalchemy.ForeignKey("posts.id")),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
)

# Create the database tables
engine = sqlalchemy.create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
metadata.create_all(engine)

# FastAPI app setup
app = FastAPI(title="Blog API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class User(BaseModel):
    id: int
    username: str

class PostCreate(BaseModel):
    title: str
    content: str

class Post(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime

class CommentCreate(BaseModel):
    content: str
    post_id: int

class Comment(BaseModel):
    id: int
    content: str
    post_id: int
    created_at: datetime

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP error occurred: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"An unexpected error occurred: {str(exc)}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred"})

# Routes
@app.post("/users", response_model=User)
async def create_user(user: User):
    logger.info(f"Creating user: {user.username}")
    query = users.insert().values(username=user.username, hashed_password="dummy_hash")
    last_record_id = await database.execute(query)
    logger.info(f"New user created: {user.username}")
    return {"id": last_record_id, "username": user.username}

@app.post("/posts", response_model=Post)
async def create_post(post: PostCreate):
    query = posts.insert().values(title=post.title, content=post.content)
    last_record_id = await database.execute(query)
    logger.info(f"New post created: {post.title}")
    return {**post.dict(), "id": last_record_id, "created_at": datetime.utcnow()}

@app.get("/posts", response_model=List[Post])
async def read_posts(skip: int = 0, limit: int = 10):
    query = posts.select().offset(skip).limit(limit)
    result = await database.fetch_all(query)
    logger.info(f"Retrieved {len(result)} posts")
    return result

@app.get("/posts/{post_id}", response_model=Post)
async def read_post(post_id: int):
    query = posts.select().where(posts.c.id == post_id)
    post = await database.fetch_one(query)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    logger.info(f"Retrieved post: {post_id}")
    return post

@app.put("/posts/{post_id}", response_model=Post)
async def update_post(post_id: int, post: PostCreate):
    query = posts.select().where(posts.c.id == post_id)
    db_post = await database.fetch_one(query)
    if db_post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    update_query = posts.update().where(posts.c.id == post_id).values(title=post.title, content=post.content)
    await database.execute(update_query)
    logger.info(f"Post updated: {post_id}")
    return {**post.dict(), "id": post_id, "created_at": db_post.created_at}

@app.delete("/posts/{post_id}", status_code=204)
async def delete_post(post_id: int):
    query = posts.select().where(posts.c.id == post_id)
    db_post = await database.fetch_one(query)
    if db_post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    delete_query = posts.delete().where(posts.c.id == post_id)
    await database.execute(delete_query)
    logger.info(f"Post deleted: {post_id}")
    return {"ok": True}

@app.post("/comments", response_model=Comment)
async def create_comment(comment: CommentCreate):
    query = comments.insert().values(content=comment.content, post_id=comment.post_id)
    last_record_id = await database.execute(query)
    logger.info(f"New comment created for post {comment.post_id}")
    return {**comment.dict(), "id": last_record_id, "created_at": datetime.utcnow()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)