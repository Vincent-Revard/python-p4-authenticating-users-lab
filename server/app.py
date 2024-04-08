#!/usr/bin/env python3

from flask import Flask, request, session
from flask_migrate import Migrate
from flask_restful import Api, Resource
from sqlalchemy import select
from werkzeug.exceptions import BadRequest, NotFound
from sqlalchemy.exc import SQLAlchemyError

from models import db, Article, User

app = Flask(__name__)
app.secret_key = b'Y\xf1Xz\x00\xad|eQ\x80t \xca\x1a\x10K'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.json.compact = False

migrate = Migrate(app, db)

db.init_app(app)
api = Api(app)

@app.errorhandler(SQLAlchemyError)
def handle_database_error(error):
    return {"error": "Database error: " + str(error)}, 500

@app.errorhandler(BadRequest)
def handle_bad_request(error):
    return {"error": "Bad request: " + str(error)}, 400

@app.errorhandler(NotFound)
def handle_not_found(error):
    return {"error": "Not found: " + str(error)}, 404

def fetch_one(model, condition):
    stmt = select(model).where(condition)
    result = db.session.execute(stmt)
    return result.scalars().first()

def paywall(f):
    def decorated(*args, **kwargs):
        session["page_views"] = (
            0 if "page_views" not in session else session["page_views"]
        )

        id = kwargs.get("id")
        if id not in session.get("viewed_articles", []):
            session.setdefault("viewed_articles", []).append(id)
        session["viewed_count"] = session.get("viewed_count", 0) + 1
        session["page_views"] += 1

        if session.get("viewed_count", 0) > 3:
            return {"message": "Maximum pageview limit reached"}, 401

        return f(*args, **kwargs)

    return decorated

class BaseResource(Resource):
    model = None

    def get(self, id=None):
        if id is None:
            instances = fetch_all(self.model)
            return [instance.to_dict() for instance in instances], 200
        else:
            instance = fetch_one(self.model, self.model.id == id)
            if instance is None:
                return {"error": f"{self.model.__name__} not found"}, 404
            return instance.to_dict(), 200

class IndexArticle(BaseResource):
    model = Article

    def get(self):
        stmt = select(Article)
        result = db.session.execute(stmt)
        articles = [article.to_dict() for article in result.scalars().all()]
        return articles, 200


class ShowArticle(BaseResource):
    model = Article
    method_decorators = [paywall]

    def get(self, id):
        if (article := fetch_one(Article, Article.id == id)) is None:
            return {"message": "Article not found."}, 404

        return article.to_dict(), 200
class ClearSession(Resource):

    def delete(self):

        session['page_views'] = None
        session['user_id'] = None

        return {}, 204

class Login(Resource):
    model = User

    def post(self):
        username = request.json.get("username")

        if (user := fetch_one(User, User.username == username)) is None:
            return {"error": "User not found"}, 404

        session["user_id"] = user.id
        return {"id": user.id, "username": user.username}, 200
class Logout(Resource):
    model = User
    def delete(self):
        session["user_id"] = None
        return {}, 204
class CheckSession(Resource):
    model = User
    
    def get(self):
        user_id = session.get("user_id")

        if not user_id:
            return {}, 401

        if (user := fetch_one(User, User.id == user_id)) is None:
            return {"error": "User not found"}, 404

        return {"id": user.id, "username": user.username}, 200

api.add_resource(ClearSession, '/clear')
api.add_resource(IndexArticle, '/articles')
api.add_resource(ShowArticle, '/articles/<int:id>')

api.add_resource(Login, "/login")
api.add_resource(Logout, "/logout")
api.add_resource(CheckSession, "/check_session")

if __name__ == '__main__':
    app.run(port=5555, debug=True)
