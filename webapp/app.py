from flask import Flask, render_template, request, send_from_directory, jsonify, session
from pymongo import MongoClient
from datetime import datetime
import secrets

app = Flask(__name__)

# MongoDB connection
client = MongoClient('mongodb://localhost:27017/')
db = client['concertron_test']  # Change this to your database name
collection = db['events']  # Change this to your collection name

app.secret_key = secrets.token_hex(16)
tag_list = db.events.distinct('tags', filter={'$or': [{'event_type': 'Concert'}, {'event_type': 'Club'}, {'event_type': 'Festival'}]})

@app.route('/')
def index():
    # Fetch data from MongoDB
    data = list(collection.find(filter={
        'event_type': 'Concert',
        'date': {'$gt': datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)}
        }, sort = {
            'date': 1
            }))  # Fetch all documents
    return render_template('index.html', data=data, collection=collection)


@app.route('/filter', methods=['POST'])
def filter_data():
    print(request.form.get('date'), str(type(request.form.get('date'))))
    filter = {
            'event_type': 'Concert',
            'date': {'$gt': datetime.now()}
            }
    for key, value in request.form.items():
        if key == 'status':
            if 'status' not in filter.keys():
                checked = request.form.getlist('status')
                if len(checked) == 1:
                    filter['status'] = checked[0]
                else:
                    filter['$or'] = [{'status': status} for status in checked]
        elif key == 'date':
            if value:
                filter['date'] = {'$gt': datetime.fromisoformat(value)}
        elif value != "NO_FILTER":
            filter[key] = value

    data = list(collection.find(filter=filter, sort={'date': 1}))
    return render_template('index.html', data=data, collection=collection)

@app.route('/images/<path:filename>', methods=['GET'])
def serve_image(filename):
    img_dir = '../img/'
    return send_from_directory(img_dir, filename)

@app.route('/tagger', methods=['GET'])
def tagger():
    session['list_index'] = 0
    while db.tags.find_one({'_id': tag_list[session['list_index']]}) is not None:
        # print(session['list_index'])
        # print(db.tags.find_one({'_id': tag_list[session['list_index']]}))
        session['list_index'] += 1
    tag = tag_list[session['list_index']]
    meta_tags = db.tags.distinct('meta_tags')
    genre_tags = db.tags.distinct('genre_tags')
    special_tags = db.tags.distinct('special_tags')
    return render_template('tagger.html', tag=tag, metas=meta_tags, genres=genre_tags, specials=special_tags)

@app.route('/tagger/submit', methods=['POST'])
def submit():
    form = request.form
    new_meta_tags = []
    new_genre_tags = []
    new_special_tags = []

    if form.get('new_meta'):
        new_meta_tags.extend(form.get('new_meta').split(', '))
    if form.get('new_genre'):
        new_genre_tags.extend(form.get('new_genre').split(', '))
    if form.get('new_special'):
        new_special_tags.extend(form.get('new_special').split(', '))
    if form.get('exist_meta'):
        new_meta_tags.extend(form.getlist('exist_meta'))
    if form.get('exist_genre'):
        new_genre_tags.extend(form.getlist('exist_genre'))
    if form.get('exist_special'):
        new_special_tags.extend(form.getlist('exist_special'))

    db.tags.insert_one({
        '_id': tag_list[session['list_index']],
        'meta_tags': new_meta_tags,
        'genre_tags': new_genre_tags,
        'special_tags': new_special_tags
        })


    meta_tags = db.tags.distinct('meta_tags')
    genre_tags = db.tags.distinct('genre_tags')
    special_tags = db.tags.distinct('special_tags')
    session['list_index'] += 1
    while db.tags.find_one({'_id': tag_list[session['list_index']]}) is not None:
        session['list_index'] += 1
    tag = tag_list[session['list_index']]
    return jsonify(tag=tag, metas=meta_tags, genres=genre_tags, specials=special_tags)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
