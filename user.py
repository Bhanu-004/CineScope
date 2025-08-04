from datetime import datetime
from database import db
from bson import ObjectId
import re
from werkzeug.security import generate_password_hash, check_password_hash

class User:
    @staticmethod
    def create_user(email, password, name, profile_emoji=None, is_child=False):
        users = db.get_users_collection()
    
        # Validation
        if not all([email, password, name]):
            raise ValueError("Email, password, and name are required")
    
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email format")
        
        if users.find_one({"email": email}):
            raise ValueError("Email already exists")
    
        # Create user with default profile
        user_data = {
            "email": email,
            "password": generate_password_hash(password),
            "name": name,
            "profile_emoji": profile_emoji or "👤",
            "is_child": is_child,
            "is_admin": False,
            "created_at": datetime.utcnow(),
            "watchlist": [],
            "profiles": [{  # Default profile
                "name": name,
                "profile_emoji": profile_emoji or "👤",
                "is_child": is_child,
                "is_default": True,
                "created_at": datetime.utcnow()
            }]
       }
    
        result = users.insert_one(user_data)
        return str(result.inserted_id)

    @staticmethod
    def ensure_default_profile(user_id):
        users = db.get_users_collection()
        user = users.find_one({"_id": ObjectId(user_id)})
        
        if user and not user.get('profiles'):
            default_profile = {
                "name": user['name'],
                "profile_emoji": user.get('profile_emoji', '👤'),
                "is_child": user.get('is_child', False),
                "is_default": True,
                "created_at": datetime.utcnow()
            }
            
            users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"profiles": [default_profile]}}
            )
            return True
        return False

    @staticmethod
    def find_by_email(email):
        return db.get_users_collection().find_one({"email": email})
    
    @staticmethod
    def find_by_id(user_id):
        users = db.get_users_collection()
        try:
            return users.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None
        
    @staticmethod
    def verify_password(user, password):
        return check_password_hash(user['password'], password)
    
    @staticmethod
    def update_preferences(user_id, preferences):
        db.get_users_collection().update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"preferred_genres": preferences}}
        )
    
    @staticmethod
    def update_profile(user_id, name, profile_emoji):
        db.get_users_collection().update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"name": name, "profile_emoji": profile_emoji}}
        )
    
    @staticmethod
    def set_reset_token(email, token, expires):
        db.get_users_collection().update_one(
            {"email": email},
            {"$set": {"reset_token": token, "reset_token_expires": expires}}
        )
    
    @staticmethod
    def find_by_reset_token(token):
        return db.get_users_collection().find_one({
            "reset_token": token,
            "reset_token_expires": {"$gt": datetime.utcnow()}
        })
    
    @staticmethod
    def update_password(user_id, new_password):
        hashed_password = generate_password_hash(new_password)
        db.get_users_collection().update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"password": hashed_password}, "$unset": {"reset_token": "", "reset_token_expires": ""}}
        )
    
    @staticmethod
    def add_to_watchlist(user_id, movie_id):
        db.get_users_collection().update_one(
            {"_id": ObjectId(user_id)},
            {"$addToSet": {"watchlist": movie_id}}
        )
    
    @staticmethod
    def remove_from_watchlist(user_id, movie_id):
        db.get_users_collection().update_one(
            {"_id": ObjectId(user_id)},
            {"$pull": {"watchlist": movie_id}}
        )

    @staticmethod
    def add_profile(user_id, profile_data):
        users = db.get_users_collection()
        profile_data['created_at'] = datetime.utcnow()
        profile_data['is_default'] = True  # Mark as default profile

        result = users.update_one(
            {"_id": ObjectId(user_id)},
            {"$push": {"profiles": profile_data}}
        )
        return result.modified_count > 0

    @staticmethod
    def get_default_profile(user_id):
        users = db.get_users_collection()
        user = users.find_one(
            {"_id": ObjectId(user_id)},
            {"profiles": {"$elemMatch": {"is_default": True}}}
        )
        return user.get('profiles', [{}])[0] if user else None

    @staticmethod
    def get_profiles(user_id):
        user = db.get_users_collection().find_one(
            {"_id": ObjectId(user_id)},
            {"profiles": 1}
        )
        return user.get('profiles', []) if user else []
    
    @staticmethod
    def add_default_profile(user_id):
        users = db.get_users_collection()
        user = users.find_one({"_id": ObjectId(user_id)})
        
        if user and not user.get('profiles'):
            default_profile = {
                "name": user['name'],
                "profile_emoji": user.get('profile_emoji', '👤'),
                "is_child": user.get('is_child', False),
                "is_default": True,
                "created_at": datetime.utcnow()
            }
            
            users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"profiles": [default_profile]}}
            )
            return True
        return False

    @staticmethod
    def get_profiles_with_fallback(user_id):
        users = db.get_users_collection()
        user = users.find_one(
            {"_id": ObjectId(user_id)},
            {"profiles": 1, "name": 1, "profile_emoji": 1, "is_child": 1}
        )
        
        if not user:
            return []
            
        if not user.get('profiles'):
            # Create default profile if missing
            default_profile = {
                "name": user['name'],
                "profile_emoji": user.get('profile_emoji', '👤'),
                "is_child": user.get('is_child', False),
                "is_default": True,
                "created_at": datetime.utcnow()
            }
            users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"profiles": [default_profile]}}
            )
            return [default_profile]
        
        return user['profiles']
