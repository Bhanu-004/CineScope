from flask import Blueprint, request, jsonify
from database import db
from fuzzywuzzy import fuzz
from flask_jwt_extended import get_jwt_identity, jwt_required

rec_routes = Blueprint('recommendations', __name__)

# --- Mood and Genre Mapping ---
MOOD_GENRE_MAP = {
    "happy": ["Comedy", "Family", "Animation", "Adventure", "Music"],
    "sad": ["Drama", "Romance", "Music", "History"],
    "excited": ["Action", "Adventure", "Thriller", "Science Fiction"],
    "scary": ["Horror", "Thriller", "Mystery"],
    "romantic": ["Romance", "Drama", "Comedy"],
    "inspiring": ["Documentary", "Biography", "Drama", "History"],
    "mystery": ["Mystery", "Crime", "Thriller", "Science Fiction"],
    "chill": ["Animation", "Family", "Comedy"],
    "dark": ["Crime", "Thriller", "Horror", "Mystery"],
    "epic": ["Adventure", "Action", "Fantasy", "War"],
    "funny": ["Comedy", "Family", "Animation"],
    "uplifting": ["Comedy", "Family", "Animation", "Music"],
    "tragic": ["Drama", "History", "War"],
    "adventurous": ["Adventure", "Action", "Fantasy"],
    "biographical": ["Biography", "Documentary", "Drama"],
    "historical": ["History", "War", "Drama"],
    "suspenseful": ["Thriller", "Mystery", "Crime"],
    "fantastical": ["Fantasy", "Science Fiction", "Adventure"],
}

# Inverse mapping for genre->mood (for future use)
GENRE_MOOD_MAP = {}
for mood, genres in MOOD_GENRE_MAP.items():
    for genre in genres:
        GENRE_MOOD_MAP.setdefault(genre, set()).add(mood)

# --- General Q&A patterns for chatbot ---
GENERAL_QA = [
    {
        "patterns": [
            "who are you", "what are you", "your name", "who made you", "what is cinescope"
        ],
        "response": "I'm CineScope's movie assistant bot! I help you discover movies and answer your questions about our platform."
    },
    {
        "patterns": [
            "how does this work", "how do i use", "how to use", "help", "what can you do"
        ],
        "response": "You can ask me for movie recommendations by genre, mood, language, or even by your favorite actor or director. Try asking: 'Recommend a happy comedy in Hindi' or 'Show me movies with Tom Hanks'."
    },
    {
        "patterns": [
            "who is the founder", "who created", "who developed"
        ],
        "response": "CineScope was developed by a passionate team of movie lovers and developers."
    },
    {
        "patterns": [
            "thank you", "thanks", "thx"
        ],
        "response": "You're welcome! Let me know if you need more movie suggestions."
    },
    {
        "patterns": [
            "hello", "hi", "hey"
        ],
        "response": "Hello! How can I help you find your next favorite movie?"
    },
    {
        "patterns": [
            "what is your favorite movie", "favorite movie"
        ],
        "response": "I love all movies equally, but I can help you find your favorite!"
    },
    {
        "patterns": [
            "can you recommend", "suggest me", "find me", "show me"
        ],
        "response": None  # These are handled by the main recommendation logic
    }
]

def check_general_qa(query):
    for qa in GENERAL_QA:
        for pattern in qa["patterns"]:
            if pattern in query:
                return qa["response"]
    return None

@rec_routes.route('/more-like-this/<int:movie_id>', methods=['GET'])
@jwt_required(optional=True)
def get_similar_movies(movie_id):
    try:
        movies_collection = db.get_movies_collection()
        users_collection = db.get_users_collection()
        current_movie = movies_collection.find_one({"id": movie_id})

        if not current_movie:
            fallback = list(movies_collection.find(
                {"poster_path": {"$exists": True}},
                {
                    "_id": 0,
                    "id": 1,
                    "title": 1,
                    "poster_path": 1,
                    "vote_average": 1,
                    "genres": 1,
                    "backdrop_path": 1,
                    "release_year": 1,
                    "overview": 1,
                    "vote_count": 1,
                    "trailer_url": 1
                }
            ).sort("vote_count", -1).limit(12))
            return jsonify(fallback)

        # --- Content-based filtering ---
        all_movies = list(movies_collection.find({
            "id": {"$ne": movie_id},
            "poster_path": {"$exists": True}
        }))

        similar_movies = []
        for movie in all_movies:
            score = 0
            # Genre similarity (Jaccard)
            if 'genres' in current_movie and 'genres' in movie:
                set1 = set(current_movie['genres'])
                set2 = set(movie['genres'])
                intersection = set1 & set2
                union = set1 | set2
                genre_score = (len(intersection) / len(union)) * 40 if union else 0
                score += genre_score
            # Director match
            if current_movie.get('director_id') and movie.get('director_id'):
                if current_movie['director_id'] == movie['director_id']:
                    score += 20
            # Cast similarity
            if 'cast_ids' in current_movie and 'cast_ids' in movie:
                common_cast = set(current_movie['cast_ids']) & set(movie['cast_ids'])
                score += min(len(common_cast), 5) * 4
            # Rating similarity
            if 'vote_average' in current_movie and 'vote_average' in movie:
                rating_diff = abs(current_movie['vote_average'] - movie['vote_average'])
                score += max(0, 10 - rating_diff)
            # Title similarity
            title_sim = fuzz.token_set_ratio(current_movie.get('title', ''), movie.get('title', ''))
            score += (title_sim / 100) * 10
            # Overview similarity
            overview_sim = fuzz.token_set_ratio(current_movie.get('overview', ''), movie.get('overview', ''))
            score += (overview_sim / 100) * 5
            # Recency bonus
            try:
                if abs(int(movie.get('release_year', 0)) - int(current_movie.get('release_year', 0))) <= 3:
                    score += 3
            except Exception:
                pass

            if score > 0:
                similar_movies.append({
                    "id": movie["id"],
                    "title": movie["title"],
                    "poster_path": movie.get("poster_path"),
                    "vote_average": movie.get("vote_average", None),
                    "genres": movie.get("genres", []),
                    "backdrop_path": movie.get("backdrop_path"),
                    "release_year": movie.get("release_year"),
                    "overview": movie.get("overview"),
                    "vote_count": movie.get("vote_count"),
                    "trailer_url": movie.get("trailer_url"),
                    "score": round(score, 2),
                    "common_genres": list(set(current_movie.get('genres', [])) & set(movie.get('genres', []))),
                    "common_cast": len(set(current_movie.get('cast_ids', [])) & set(movie.get('cast_ids', [])))
                })

        # --- Collaborative filtering ---
        collab_movies = []
        user_id = get_jwt_identity()
        if user_id:
            similar_users = users_collection.find({"liked_movies": movie_id})
            collab_movie_ids = set()
            for sim_user in similar_users:
                for mid in sim_user.get("liked_movies", []):
                    if mid != movie_id:
                        collab_movie_ids.add(mid)
            if collab_movie_ids:
                collab_movies = list(movies_collection.find(
                    {"id": {"$in": list(collab_movie_ids)}, "poster_path": {"$exists": True}},
                    {
                        "_id": 0,
                        "id": 1,
                        "title": 1,
                        "poster_path": 1,
                        "vote_average": 1,
                        "genres": 1,
                        "backdrop_path": 1,
                        "release_year": 1,
                        "overview": 1,
                        "vote_count": 1,
                        "trailer_url": 1
                    }
                ))

        # --- Hybrid: Merge, deduplicate, and rank ---
        all_results = {m['id']: m for m in similar_movies}
        for m in collab_movies:
            if m['id'] not in all_results:
                m['score'] = 100  # Boost collaborative results
                all_results[m['id']] = m
            else:
                all_results[m['id']]['score'] += 30  # Boost if both

        results = sorted(all_results.values(), key=lambda x: x.get('score', 0), reverse=True)[:12]

        if not results:
            fallback = list(movies_collection.find(
                {"id": {"$ne": movie_id}, "poster_path": {"$exists": True}},
                {
                    "_id": 0,
                    "id": 1,
                    "title": 1,
                    "poster_path": 1,
                    "vote_average": 1,
                    "genres": 1,
                    "backdrop_path": 1,
                    "release_year": 1,
                    "overview": 1,
                    "vote_count": 1,
                    "trailer_url": 1
                }
            ).sort("vote_count", -1).limit(12))
            return jsonify(fallback)

        return jsonify(results)

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@rec_routes.route('/chat', methods=['POST'])
@jwt_required(optional=True)
def chat_recommendations():
    import random
    try:
        data = request.get_json()
        query = (data.get('query') or '').lower()
        preferences = data.get('preferences', {})
        user_id = get_jwt_identity()

        # --- General Q&A: handle before movie logic ---
        general_response = check_general_qa(query)
        if general_response is not None:
            return jsonify({
                "results": [],
                "message": general_response,
                "found_genres": [],
                "found_people": [],
                "detected_moods": [],
                "found_languages": [],
                "liked_movies": [],
                "disliked_movies": []
            })

        movies_collection = db.get_movies_collection()
        users_collection = db.get_users_collection()
        people_collection = db.get_people_collection()

        # --- Mood extraction (multi-mood, robust) ---
        mood_keywords = {}
        for mood, keywords in MOOD_GENRE_MAP.items():
            mood_keywords[mood] = [mood] + [k.lower() for k in keywords]
        detected_moods = []
        for mood, keywords in mood_keywords.items():
            if any(word in query for word in keywords):
                detected_moods.append(mood)
        # Also check for explicit mood in preferences
        if preferences.get('mood'):
            pref_mood = preferences['mood'].lower()
            if pref_mood in MOOD_GENRE_MAP and pref_mood not in detected_moods:
                detected_moods.append(pref_mood)

        # --- Genre extraction (multiple) ---
        genre_mapping = {g.lower(): g for g in [
            "Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary", "Drama",
            "Family", "Fantasy", "History", "Horror", "Music", "Mystery", "Romance",
            "Science Fiction", "Thriller", "War", "Western", "Biography"
        ]}
        found_genres = []
        for g in genre_mapping:
            if g in query or preferences.get('genre', '').lower() == g:
                found_genres.append(genre_mapping[g])
        # Add genres from detected moods
        for mood in detected_moods:
            for genre in MOOD_GENRE_MAP.get(mood, []):
                if genre not in found_genres:
                    found_genres.append(genre)

        # --- Language extraction (multiple, robust) ---
        language_keywords = {
            "en": ["english", "hollywood"],
            "hi": ["hindi", "bollywood"],
            "te": ["telugu", "tollywood", "te"],
            "ta": ["tamil", "kollywood", "ta"],
            "ml": ["malayalam", "ml"],
            "kn": ["kannada", "kn"],
        }
        found_languages = []
        for lang, keywords in language_keywords.items():
            if any(word in query for word in keywords) or preferences.get('language', '').lower() in keywords or preferences.get('language', '').lower() == lang:
                found_languages.append(lang)

        # --- Person extraction (multiple, fuzzy, cast & director) ---
        found_people = []
        all_people = list(people_collection.find({}, {"name": 1, "id": 1}))
        for person in all_people:
            pname = person['name'].lower()
            if fuzz.partial_ratio(pname, query) > 85 or fuzz.partial_ratio(query, pname) > 85:
                found_people.append(person['name'])
            elif preferences.get('person'):
                if fuzz.partial_ratio(pname, preferences.get('person', '').lower()) > 85:
                    found_people.append(person['name'])

        # --- Like/Dislike extraction for chatbot ---
        liked_movies = []
        disliked_movies = []
        user_liked_ids = set()
        user_disliked_ids = set()
        if user_id:
            user = users_collection.find_one({"_id": user_id})
            if user:
                user_liked_ids = set(user.get("liked_movies", []))
                user_disliked_ids = set(user.get("disliked_movies", []))
                liked_movies = list(user_liked_ids)
                disliked_movies = list(user_disliked_ids)

        # --- Build MongoDB filter ---
        filters = []
        if found_genres:
            filters.append({"genres": {"$in": found_genres}})
        if found_people:
            people_ids = [p['id'] for p in all_people if p['name'] in found_people]
            # Match both cast and director
            filters.append({"$or": [
                {"cast_ids": {"$in": people_ids}},
                {"director_id": {"$in": people_ids}}
            ]})
        if found_languages:
            filters.append({"original_language": {"$in": found_languages}})
        # Mood-based genre mapping (already included above, but keep for clarity)
        for mood in detected_moods:
            if mood in MOOD_GENRE_MAP:
                filters.append({"genres": {"$in": MOOD_GENRE_MAP[mood]}})
        # Exclude disliked movies for logged-in users
        if user_disliked_ids:
            filters.append({"id": {"$nin": list(user_disliked_ids)}})

        mongo_filter = {"vote_count": {"$gt": 5}, "poster_path": {"$exists": True}}
        if filters:
            mongo_filter = {"$and": [mongo_filter] + filters}

        # --- Detect "top" or "best" in query for sorting ---
        sort_criteria = [("vote_average", -1), ("vote_count", -1)]
        if "top" in query or "best" in query:
            sort_criteria = [("vote_average", -1), ("vote_count", -1)]
        elif "new" in query or "latest" in query:
            sort_criteria = [("release_year", -1), ("vote_count", -1)]

        # --- Query movies (content-based) ---
        movies = list(movies_collection.find(
            mongo_filter,
            {
                "_id": 0,
                "id": 1,
                "title": 1,
                "poster_path": 1,
                "backdrop_path": 1,
                "release_year": 1,
                "vote_average": 1,
                "vote_count": 1,
                "genres": 1,
                "overview": 1,
                "trailer_url": 1,
                "original_language": 1
            }
        ).sort(sort_criteria).limit(24))

        # --- If nothing found, try relaxing filters (e.g., drop genre, keep language) ---
        if not movies and found_languages:
            relaxed_filter = {"original_language": {"$in": found_languages}, "poster_path": {"$exists": True}}
            if user_disliked_ids:
                relaxed_filter["id"] = {"$nin": list(user_disliked_ids)}
            movies = list(movies_collection.find(
                relaxed_filter,
                {
                    "_id": 0,
                    "id": 1,
                    "title": 1,
                    "poster_path": 1,
                    "backdrop_path": 1,
                    "release_year": 1,
                    "vote_average": 1,
                    "vote_count": 1,
                    "genres": 1,
                    "overview": 1,
                    "trailer_url": 1,
                    "original_language": 1
                }
            ).sort(sort_criteria).limit(24))

        # --- Collaborative filtering (for logged-in users) ---
        collab_movies = []
        if user_id:
            user = users_collection.find_one({"_id": user_id})
            if user and user.get("liked_movies"):
                similar_users = users_collection.find({
                    "liked_movies": {"$in": user["liked_movies"]},
                    "_id": {"$ne": user_id}
                })
                liked_set = set(user["liked_movies"])
                collab_movie_ids = set()
                for sim_user in similar_users:
                    for mid in sim_user.get("liked_movies", []):
                        if mid not in liked_set and mid not in user_disliked_ids:
                            collab_movie_ids.add(mid)
                if collab_movie_ids:
                    collab_movies = list(movies_collection.find(
                        {"id": {"$in": list(collab_movie_ids)}, "poster_path": {"$exists": True}},
                        {
                            "_id": 0,
                            "id": 1,
                            "title": 1,
                            "poster_path": 1,
                            "backdrop_path": 1,
                            "release_year": 1,
                            "vote_average": 1,
                            "vote_count": 1,
                            "genres": 1,
                            "overview": 1,
                            "trailer_url": 1,
                            "original_language": 1
                        }
                    ).sort(sort_criteria).limit(24))

        # --- Hybrid: Merge, deduplicate, and rank ---
        all_movies = {m['id']: m for m in movies}
        for m in collab_movies:
            all_movies[m['id']] = m
        results = list(all_movies.values())[:12]

        # --- Mark liked/disliked in results for chatbot UI ---
        for m in results:
            m['liked'] = m['id'] in user_liked_ids
            m['disliked'] = m['id'] in user_disliked_ids

        # --- Dynamic, conversational message (short and friendly) ---
        greetings = [
            "Here's something you might love!",
            "Check these out!",
            "I've picked these for you!",
            "Hope you find your next favorite movie!",
            "Enjoy these recommendations!",
            "Let me know if you want something different!"
        ]
        message_parts = []
        if found_people:
            message_parts.append("movies with your favorite actors or directors")
        if found_genres:
            message_parts.append(f"{', '.join(found_genres)} movies")
        if detected_moods:
            message_parts.append(f"for a {', '.join(detected_moods)} mood")
        if found_languages:
            lang_display = {
                "en": "English", "hi": "Hindi", "te": "Telugu", "ta": "Tamil", "ml": "Malayalam",
                "kn": "Kannada", "fr": "French", "es": "Spanish", "de": "German", "ja": "Japanese",
                "ko": "Korean", "zh": "Chinese", "it": "Italian", "ru": "Russian", "bn": "Bengali",
                "mr": "Marathi", "pa": "Punjabi", "gu": "Gujarati", "ur": "Urdu"
            }
            display_langs = [lang_display.get(l, l.capitalize()) for l in found_languages]
            message_parts.append(f"in {', '.join(display_langs)}")

        if message_parts:
            message = f"{random.choice(greetings)} Here are some " + ", ".join(message_parts) + "!"
        elif user_id and results:
            message = f"{random.choice(greetings)} Based on your likes and similar users, you might enjoy these movies!"
        else:
            message = f"{random.choice(greetings)} Here are some popular movies you might enjoy!"

        # Fallback: if nothing found, return trending/popular movies
        if not results:
            fallback_filter = {"vote_count": {"$gt": 5}, "poster_path": {"$exists": True}}
            if user_disliked_ids:
                fallback_filter["id"] = {"$nin": list(user_disliked_ids)}
            results = list(movies_collection.find(
                fallback_filter,
                {
                    "_id": 0,
                    "id": 1,
                    "title": 1,
                    "poster_path": 1,
                    "backdrop_path": 1,
                    "release_year": 1,
                    "vote_average": 1,
                    "vote_count": 1,
                    "genres": 1,
                    "overview": 1,
                    "trailer_url": 1,
                    "original_language": 1
                }
            ).sort(sort_criteria).limit(12))
            for m in results:
                m['liked'] = m['id'] in user_liked_ids
                m['disliked'] = m['id'] in user_disliked_ids
            message = "Sorry, I couldn't find any matches for your request. Here are some popular movies instead!"

        response = {
            "results": results,
            "found_genres": found_genres,
            "found_people": found_people,
            "detected_moods": detected_moods,
            "found_languages": found_languages,
            "liked_movies": liked_movies,
            "disliked_movies": disliked_movies,
            "message": message
        }

        return jsonify(response)

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500