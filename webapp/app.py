from flask import Flask, render_template, request
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)

# MongoDB connection
client = MongoClient('mongodb://localhost:27017/')
db = client['concertron_test']  # Change this to your database name
collection = db['events']  # Change this to your collection name


@app.route('/')
def index():
    # Fetch data from MongoDB
    data = list(collection.find(filter={
        'event_type': 'Concert',
        'date': {'$gt': datetime.today()}
        }, sort = {
            'date': 1
            }))  # Fetch all documents
    return render_template('index.html', data=data, collection=collection)


@app.route('/filter', methods=['POST'])
def filter_data():
    print(request.form.get('date'), str(type(request.form.get('date'))))
    filter = {
            'event_type': 'Concert',
            'date': {'$gt': datetime.today()}
            }
    for key, value in request.form.items():
        if key == 'status':
            if 'status' not in filter.keys():
                checked = request.form.getlist('status')
                if len(checked) == 1:
                    filter['status'] = checked[0]
                else:
                    filter['$or'] = [{'status': status} for status in checked]
                    # select = []
                    # for status in checked:
                        # select.append({'status': status})
                    # filter.update({'$or': select})
        elif key == 'date':
            if value:
                filter['date'] = {'$gt': datetime.fromisoformat(value)}
        elif value != "NO_FILTER":
            filter[key] = value

    data = list(collection.find(filter=filter, sort={'date': 1}))
    return render_template('index.html', data=data, collection=collection)


if __name__ == '__main__':
    app.run(debug=True)
