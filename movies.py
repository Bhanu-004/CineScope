from flask import Blueprint, jsonify, request
from database import db
from fuzzywuzzy import fuzz
from datetime import datetime

movie_routes = Blueprint('movies', __name__)

@movie_routes.route('/by-genre/<genre>', methods=['GET'])
def get_movies_by_genre(genre):
    movies_collection = db.get_movies_collection()
    try:
        genre_mapping = {
            'action': 'Action',
            'adventure': 'Adventure',
            'animation': 'Animation',
            'comedy': 'Comedy',
            'crime': 'Crime',
            'documentary': 'Documentary',
            'drama': 'Drama',
            'family': 'Family',
            'fantasy': 'Fantasy',
            'history': 'History',
            'horror': 'Horror',
            'music': 'Music',
            'mystery': 'Mystery',
            'romance': 'Romance',
            'scifi': 'Science Fiction',
            'thriller': 'Thriller',
            'war': 'War',
            'western': 'Western'
        }
        normalized_genre = genre_mapping.get(genre.lower(), genre)
        pipeline = [
            {
                "$match": {
                    "genres": normalized_genre,
                    "vote_count": {"$gt": 25},
                    "poster_path": {"$exists": True}
                }
            },
            {
                "$addFields": {
                    "genre_match_score": {
                        "$cond": [
                            {"$eq": [{"$arrayElemAt": ["$genres", 0]}, normalized_genre]},
                            3,
                            {"$cond": [
                                {"$eq": [{"$arrayElemAt": ["$genres", 1]}, normalized_genre]},
                                2,
                                1
                            ]}
                        ]
                    }
                }
            },
            {
                "$sort": {
                    "genre_match_score": -1,
                    "vote_average": -1,
                    "vote_count": -1
                }
            },
            {
                "$limit": 7000
            },
            {
                "$project": {
                    "_id": 0,
                    "id": 1,
                    "title": 1,
                    "poster_path": 1,
                    "release_year": 1,
                    "vote_average": 1,
                    "vote_count": 1,
                    "backdrop_path": 1
                }
            }
        ]
        movies = list(movies_collection.aggregate(pipeline))
        if not movies:
            return jsonify({"error": f"No {normalized_genre} movies found"}), 404
        return jsonify(movies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@movie_routes.route('/popular', methods=['GET'])
def get_popular_movies():
    movies_collection = db.get_movies_collection()
    try:
        movies = list(movies_collection.find(
            {
                "vote_count": {"$gt": 75},
                "release_year": {"$regex": "^(200|201|202)"},
                "id": {"$exists": True},
                "title": {"$exists": True},
                "poster_path": {"$exists": True}
            },
            {
                "_id": 0,
                "id": 1,
                "title": 1,
                "poster_path": 1,
                "release_year": 1,
                "vote_average": 1,
                "vote_count": 1,
                "backdrop_path": 1
            }
        ).sort("vote_count", -1).limit(150))
        if not movies:
            return jsonify({"error": "No popular movies found"}), 404
        return jsonify(movies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@movie_routes.route('/by-genre-language', methods=['GET'])
def get_movies_by_genre_language():
    genre = request.args.get('genre')
    language = request.args.get('language')
    if not genre or not language:
        return jsonify({"error": "Genre and language required"}), 400
    movies_collection = db.get_movies_collection()
    try:
        movies = list(movies_collection.find(
            {
                "genres": genre,
                "language": {"$regex": f"^{language}$", "$options": "i"},
                "poster_path": {"$exists": True},
                "id": {"$exists": True},
                "title": {"$exists": True}
            },
            {
                "_id": 0,
                "id": 1,
                "title": 1,
                "poster_path": 1,
                "release_year": 1,
                "vote_average": 1,
                "vote_count": 1,
                "backdrop_path": 1,
                "language": 1
            }
        ).sort("vote_count", -1).limit(100))
        return jsonify(movies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@movie_routes.route('/by-decade/<decade>', methods=['GET'])
def get_movies_by_decade(decade):
    movies_collection = db.get_movies_collection()
    try:
        start_year = int(decade)
        end_year = start_year + 9
        movies = list(movies_collection.find(
            {
                "release_year": {"$gte": str(start_year), "$lte": str(end_year)},
                "poster_path": {"$exists": True},
                "id": {"$exists": True},
                "title": {"$exists": True}
            },
            {
                "_id": 0,
                "id": 1,
                "title": 1,
                "poster_path": 1,
                "release_year": 1,
                "vote_average": 1,
                "vote_count": 1,
                "backdrop_path": 1
            }
        ).sort("vote_count", -1).limit(30))
        return jsonify(movies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@movie_routes.route('/by-decade-language/<decade>/<language>', methods=['GET'])
def get_movies_by_decade_language(decade, language):
    movies_collection = db.get_movies_collection()
    try:
        start_year = int(decade)
        end_year = start_year + 9
        movies = list(movies_collection.find(
            {
                "release_year": {"$gte": str(start_year), "$lte": str(end_year)},
                "language": {"$regex": f"^{language}$", "$options": "i"},
                "poster_path": {"$exists": True},
                "id": {"$exists": True},
                "title": {"$exists": True}
            },
            {
                "_id": 0,
                "id": 1,
                "title": 1,
                "poster_path": 1,
                "release_year": 1,
                "vote_average": 1,
                "vote_count": 1,
                "backdrop_path": 1,
                "language": 1
            }
        ).sort("vote_count", -1).limit(30))
        return jsonify(movies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@movie_routes.route('/search', methods=['GET'])
def search_movies():
    movies_collection = db.get_movies_collection()
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify([])
    try:
        all_movies = list(movies_collection.find({}, {
            "_id": 0,
            "id": 1,
            "title": 1,
            "original_title": 1,
            "poster_path": 1,
            "release_year": 1,
            "vote_average": 1
        }))
        matched_movies = []
        for movie in all_movies:
            title_score = fuzz.token_set_ratio(query, movie.get('title', '').lower())
            original_score = fuzz.token_set_ratio(query, movie.get('original_title', '').lower())
            if title_score > 60 or original_score > 60:
                matched_movies.append({
                    **movie,
                    'match_score': max(title_score, original_score)
                })
        matched_movies.sort(key=lambda x: x['match_score'], reverse=True)
        results = []
        for movie in matched_movies[:30]:
            movie.pop('match_score', None)
            results.append(movie)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@movie_routes.route('/by-language/<language>', methods=['GET'])
def get_movies_by_language(language):
    movies_collection = db.get_movies_collection()
    try:
        movies = list(movies_collection.find(
            {"language": {"$regex": f"^{language}$", "$options": "i"}},
            {
                "_id": 0,
                "id": 1,
                "title": 1,
                "poster_path": 1,
                "release_year": 1,
                "vote_average": 1,
                "vote_count": 1,
                "backdrop_path": 1
            }
        ).sort("vote_count", -1).limit(100))
        return jsonify(movies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@movie_routes.route('/<int:movie_id>', methods=['GET'])
def get_movie_details(movie_id):
    movies_collection = db.get_movies_collection()
    people_collection = db.get_people_collection()
    try:
        movie = movies_collection.find_one(
            {"id": movie_id},
            {"_id": 0}
        )
        if not movie:
            return jsonify({"error": "Movie not found"}), 404
        cast = []
        for cast_id in movie.get('cast_ids', []):
            person = people_collection.find_one(
                {"id": cast_id},
                {"_id": 0, "id": 1, "name": 1, "profile_path": 1, "characters": 1}
            )
            if person:
                character = next(
                    (c['name'] for c in person.get('characters', []) 
                    if c['movie'] == movie['title']), 
                    'Unknown'
                )
                cast.append({
                    "id": person['id'],
                    "name": person['name'],
                    "profile_path": person['profile_path'],
                    "character": character
                })
        movie['cast'] = cast
        if 'director_id' in movie:
            director = people_collection.find_one(
                {"id": movie['director_id']},
                {"_id": 0, "id": 1, "name": 1, "profile_path": 1}
            )
            if director:
                movie['director'] = director
        if 'producer_ids' in movie:
            producers = list(people_collection.find(
                {"id": {"$in": movie['producer_ids']}},
                {"_id": 0, "id": 1, "name": 1, "profile_path": 1}
            ))
            if producers:
                movie['producers'] = producers
        return jsonify(movie)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@movie_routes.route('/free', methods=['GET'])
def get_free_movies():
    movies_collection = db.get_movies_collection()
    try:
        movies = list(movies_collection.find(
            {
                "movie_url": {"$exists": True, "$ne": ""},
                "poster_path": {"$exists": True},
                "id": {"$exists": True},
                "title": {"$exists": True}
            },
            {
                "_id": 0,
                "id": 1,
                "title": 1,
                "poster_path": 1,
                "release_year": 1,
                "vote_average": 1,
                "vote_count": 1,
                "backdrop_path": 1,
                "movie_url": 1
            }
        ).sort("vote_count", -1).limit(30))
        return jsonify(movies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@movie_routes.route('/new-releases', methods=['GET'])
def get_new_releases():
    movies_collection = db.get_movies_collection()
    current_year = str(datetime.now().year)
    try:
        movies = list(movies_collection.find(
            {
                "release_year": current_year,
                "poster_path": {"$exists": True},
                "id": {"$exists": True},
                "title": {"$exists": True}
            },
            {
                "_id": 0,
                "id": 1,
                "title": 1,
                "poster_path": 1,
                "release_year": 1,
                "vote_average": 1,
                "vote_count": 1,
                "backdrop_path": 1
            }
        ).sort("vote_count", -1).limit(20))
        return jsonify(movies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500