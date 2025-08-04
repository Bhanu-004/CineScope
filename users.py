from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from models.user import User
from database import db
from bson import ObjectId
from datetime import datetime
from werkzeug.security import generate_password_hash

user_routes = Blueprint('user', __name__)

# ---- Basic Profile ----
@user_routes.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    user = User.find_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "name": user["name"],
        "email": user["email"],
        "profile_emoji": user.get("profile_emoji", "👤"),
        "is_child": user.get("is_child", False),
        "is_admin": user.get("is_admin", False),
        "profiles": user.get("profiles", [])
    }), 200

@user_routes.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    data = request.get_json()
    name = data.get('name')
    profile_emoji = data.get('profile_emoji')
    if not name or not profile_emoji:
        return jsonify({"error": "Name and profile emoji are required"}), 400
    User.update_profile(user_id, name, profile_emoji)
    return jsonify({"message": "Profile updated successfully"}), 200

# ---- Preferences ----
@user_routes.route('/preferences/<int:profile_idx>', methods=['PUT'])
@jwt_required()
def update_profile_preferences_by_index(profile_idx):
    user_id = get_jwt_identity()
    genres = request.json.get('preferred_genres', [])
    languages = request.json.get('preferred_languages', [])
    if not isinstance(genres, list) or not isinstance(languages, list):
        return jsonify({"error": "Preferred genres and languages must be arrays"}), 400
    users = db.get_users_collection()
    user = users.find_one({"_id": ObjectId(user_id)})
    if not user or not user.get('profiles') or profile_idx >= len(user['profiles']):
        return jsonify({"error": "Profile not found"}), 404
    users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            f"profiles.{profile_idx}.preferred_genres": genres,
            f"profiles.{profile_idx}.preferred_languages": languages
        }}
    )
    return jsonify({"message": "Preferences updated successfully"}), 200

# ---- Watchlist ----
@user_routes.route('/watchlist/<int:profile_idx>', methods=['GET'])
@jwt_required()
def get_profile_watchlist(profile_idx):
    user_id = get_jwt_identity()
    user = User.find_by_id(user_id)
    if not user or not user.get('profiles') or profile_idx >= len(user['profiles']):
        return jsonify({"error": "Profile not found"}), 404
    profile = user['profiles'][profile_idx]
    movies_collection = db.get_movies_collection()
    watchlist_movies = list(movies_collection.find(
        {"id": {"$in": profile.get("watchlist", [])}},
        {"_id": 0, "id": 1, "title": 1, "poster_path": 1, "release_year": 1, "vote_average": 1}
    ))
    return jsonify(watchlist_movies), 200

@user_routes.route('/watchlist/<int:profile_idx>/<int:movie_id>', methods=['POST'])
@jwt_required()
def add_to_profile_watchlist(profile_idx, movie_id):
    user_id = get_jwt_identity()
    users = db.get_users_collection()
    user = users.find_one({"_id": ObjectId(user_id)})
    if not user or not user.get('profiles') or profile_idx >= len(user['profiles']):
        return jsonify({"error": "Profile not found"}), 404
    users.update_one(
        {"_id": ObjectId(user_id)},
        {"$addToSet": {f"profiles.{profile_idx}.watchlist": movie_id}}
    )
    return jsonify({"message": "Added to watchlist"}), 200

@user_routes.route('/watchlist/<int:profile_idx>/<int:movie_id>', methods=['DELETE'])
@jwt_required()
def remove_from_profile_watchlist(profile_idx, movie_id):
    user_id = get_jwt_identity()
    users = db.get_users_collection()
    user = users.find_one({"_id": ObjectId(user_id)})
    if not user or not user.get('profiles') or profile_idx >= len(user['profiles']):
        return jsonify({"error": "Profile not found"}), 404
    users.update_one(
        {"_id": ObjectId(user_id)},
        {"$pull": {f"profiles.{profile_idx}.watchlist": movie_id}}
    )
    return jsonify({"message": "Removed from watchlist"}), 200

# ---- Account Management ----
@user_routes.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    profile_emoji = data.get('profile_emoji', '👤')
    accepted_terms = data.get('accepted_terms', False)

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400
    if not accepted_terms:
        return jsonify({"error": "You must accept the terms and conditions"}), 400

    users = db.get_users_collection()
    if users.find_one({"email": email}):
        return jsonify({"error": "Email already registered"}), 400

    hashed_password = generate_password_hash(password)
    user_doc = {
        "name": name,
        "email": email,
        "password": hashed_password,
        "profile_emoji": profile_emoji,
        "accepted_terms": accepted_terms,
        "is_child": False,
        "is_admin": False,
        "profiles": [
            {
                "name": name,
                "profile_emoji": profile_emoji,
                "is_child": False,
                "is_default": True,
                "created_at": datetime.utcnow(),
                "preferred_genres": [],
                "preferred_languages": [],
                "watchlist": []
            }
        ],
        "liked_movies": [],
        "created_at": datetime.utcnow()
    }
    result = users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    access_token = create_access_token(identity=user_id)
    return jsonify({
        "access_token": access_token,
        "user": {
            "name": name,
            "profile_emoji": profile_emoji,
            "is_child": False
        }
    }), 200

@user_routes.route('/profiles', methods=['GET'])
@jwt_required()
def get_user_profiles():
    user_id = get_jwt_identity()
    user = User.find_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.get('profiles', [])), 200

@user_routes.route('/like/<int:movie_id>', methods=['POST'])
@jwt_required()
def like_movie(movie_id):
    user_id = get_jwt_identity()
    db.get_users_collection().update_one(
        {"_id": ObjectId(user_id)},
        {"$addToSet": {"liked_movies": movie_id}}
    )
    return jsonify({"message": "Liked!"}), 200

@user_routes.route('/dislike/<int:movie_id>', methods=['POST'])
@jwt_required()
def dislike_movie(movie_id):
    user_id = get_jwt_identity()
    db.get_users_collection().update_one(
        {"_id": ObjectId(user_id)},
        {"$pull": {"liked_movies": movie_id}}
    )
    return jsonify({"message": "Disliked!"}), 200

@user_routes.route('/likes', methods=['GET'])
@jwt_required()
def get_liked_movies():
    user_id = get_jwt_identity()
    user = db.get_users_collection().find_one({"_id": ObjectId(user_id)})
    liked = user.get("liked_movies", [])
    movies = list(db.get_movies_collection().find({"id": {"$in": liked}}, {"_id": 0}))
    return jsonify(movies), 200

@user_routes.route('/profiles', methods=['POST'])
@jwt_required()
def create_profile():
    user_id = get_jwt_identity()
    data = request.get_json()
    new_profile = {
        "name": data.get('name'),
        "profile_emoji": data.get('profile_emoji', '👤'),
        "is_child": data.get('is_child', False),
        "is_default": False,
        "created_at": datetime.utcnow(),
        "preferred_genres": [],
        "preferred_languages": [],
        "watchlist": []
    }
    users = db.get_users_collection()
    result = users.update_one(
        {"_id": ObjectId(user_id)},
        {"$push": {"profiles": new_profile}}
    )
    if result.modified_count > 0:
        return jsonify(new_profile), 201
    else:
        return jsonify({"error": "Failed to create profile"}), 400

@user_routes.route('/reset-password', methods=['POST'])
@jwt_required()
def reset_password():
    user_id = get_jwt_identity()
    data = request.get_json()
    new_password = data.get('new_password')
    if not new_password or len(new_password) < 4:
        return jsonify({"error": "Password must be at least 4 characters"}), 400
    users = db.get_users_collection()
    hashed_password = generate_password_hash(new_password)
    result = users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password": hashed_password}}
    )
    if result.matched_count > 0:
        return jsonify({"message": "Password reset successfully"}), 200
    else:
        return jsonify({"error": "Failed to reset password"}), 400

@user_routes.route('/watchlist', methods=['GET'])
@jwt_required()
def get_default_profile_watchlist():
    user_id = get_jwt_identity()
    users = db.get_users_collection()
    user = users.find_one({"_id": ObjectId(user_id)})

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Find default profile
    profiles = user.get("profiles", [])
    default_profile = next((p for p in profiles if p.get("is_default")), None)

    if not default_profile:
        return jsonify({"error": "Default profile not found"}), 404

    return jsonify(default_profile.get("watchlist", [])), 200


@user_routes.route('/profile/<int:profile_idx>', methods=['PUT'])
@jwt_required()
def update_profile_by_index(profile_idx):
    user_id = get_jwt_identity()
    data = request.get_json()
    name = data.get('name')
    profile_emoji = data.get('profile_emoji')
    if not name or not profile_emoji:
        return jsonify({"error": "Name and profile emoji are required"}), 400
    users = db.get_users_collection()
    user = users.find_one({"_id": ObjectId(user_id)})
    if not user or not user.get('profiles') or profile_idx >= len(user['profiles']):
        return jsonify({"error": "Profile not found"}), 404
    users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            f"profiles.{profile_idx}.name": name,
            f"profiles.{profile_idx}.profile_emoji": profile_emoji
        }}
    )
    return jsonify({"message": "Profile updated successfully"}), 200