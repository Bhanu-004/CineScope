from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token
from models.user import User

auth_routes = Blueprint('auth', __name__)

@auth_routes.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        required_fields = ['email', 'password', 'name', 'accepted_terms']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400
        if not data['accepted_terms']:
            return jsonify({"error": "You must accept terms and conditions"}), 400

        user_id = User.create_user(
            email=data['email'],
            password=data['password'],
            name=data['name'],
            profile_emoji=data.get('profile_emoji', '👤'),
            is_child=data.get('is_child', False)
        )

        access_token = create_access_token(identity=user_id)
        refresh_token = create_refresh_token(identity=user_id)

        return jsonify({
            "message": "User registered successfully",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": user_id
        }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(e)
        return jsonify({"error": "Registration failed"}), 500

@auth_routes.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.find_by_email(data['email'])
    if not user or not User.verify_password(user, data['password']):
        return jsonify({"error": "Invalid credentials"}), 401

    # Ensure default profile exists
    User.ensure_default_profile(str(user['_id']))

    response_data = {
        "access_token": create_access_token(identity=str(user['_id'])),
        "user": {
            "id": str(user['_id']),
            "name": user['name'],
            "email": user['email'],
            "is_admin": user.get('is_admin', False)
        }
    }

    return jsonify(response_data), 200