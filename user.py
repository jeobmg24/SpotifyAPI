from flask import Flask, redirect, request, jsonify, session, render_template, url_for
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv
import urllib.parse
import json

app = Flask(__name__)
app.secret_key = 'secret_key'

load_dotenv()
# I put the client id and secret in a .env file. Therefore I use os.getenv to retrieve them
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = 'http://localhost:5000/callback'

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1'


@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login')
def login():
    # defining the scope that this app will need from the users spotify account
    scope = 'user-read-private user-read-email user-top-read'
    
    # parameters that are needed to get authorization
    params = {
        'client_id': CLIENT_ID, 
        'response_type':'code',  
        'scope': scope, 
        'redirect_uri': REDIRECT_URI, 
        'show_dialog': True # only for debugging
    }
    
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    
    return redirect(auth_url)

@app.route('/home')
def home():
    return render_template('home_of_app.html')

@app.route('/callback')
def callback():
    """This function is used to get an authorization token and save it in the session 
        Input: None
        Output: None"""
    if 'error' in request.args:
        return jsonify({"error": request.args['error']}) # show error message if there is an error
    
    if 'code' in request.args:
        req_body = {
            'code': request.args['code'], 
            'grant_type': 'authorization_code', 
            'redirect_uri': REDIRECT_URI, 
            'client_id': CLIENT_ID, 
            'client_secret': CLIENT_SECRET
        }
        
        response = requests.post(TOKEN_URL, data=req_body)
        token_info = response.json()
        # get the access token, refresh token, and time it expires (24 hours from now)
        session['access_token'] = token_info['access_token']
        session['refresh_token'] =  token_info['refresh_token']
        session['expires_at'] =  datetime.now().timestamp() + token_info['expires_in']
        # if everything goes corectly, redirect the user to the home
        return redirect(url_for('home'))
    
    
    
@app.route('/artists')
def get_top_artists():
    """This function is used to run the artists.html page"""
    # if there is no access token, guide the user to login again
    if 'access_token' not in session:
        return redirect('/login')
    # if the token has expired, guide the user to get another token
    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')
    # define the headers, we will have to use these for any request that we make to the spotify api
    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }
    
    response = requests.get(API_BASE_URL + '/me/top/artists', headers=headers) # this is the page where we get users top artists
    # status code of 200 means that the request was successful
    if response.status_code == 200:
        response_data = response.json()
        artists = [] # we will keep all of our information about artists in this list
        for artist in response_data['items']: #iterate through the items response
            artist_name = artist['name']
            artist_picture = artist['images'][0]['url'] if artist['images'] else None # get first picture of artist
            popularity = artist['popularity']
            genres = artist['genres']
            # for every artist, keep a dictionary about all their data
            artist_data = {
                'name': artist_name,
                'picture': artist_picture,
                'popularity': popularity,
                'genres': genres
            }

            artists.append(artist_data)
        # the html page will now be passed the artists list which will be shown
        return render_template('artists.html', artists=artists)
    
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return redirect('/login')


@app.route('/tracks')
def get_top_tracks():
    """This function is used to run the tracks.html page"""
    if 'access_token' not in session:
        return redirect('/login')
    
    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')
    
    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }
    
    response = requests.get(API_BASE_URL + '/me/top/tracks', headers=headers)
    if response.status_code == 200:
        response_data = response.json()
        tracks = []
        for track in response_data['items']:
            track_name = track['name']
            track_length = track['duration_ms']
            total_seconds = track_length / 1000 # get the seconds
            minutes = total_seconds // 60 # divide the amount of seconds down by 60 to get the minutes
            seconds = total_seconds - (minutes * 60) #          
            print(f'seconds: {seconds}')
            popularity = track['popularity']
            artists = track['artists']
            print()
            all = []
            for x in artists:
                name = x['name']
                all.append(name)
                

            track_data = {
                'name': track_name,
                'time': f"{str(int(minutes))}::{str(round(seconds, 2))}",
                'popularity': popularity,
                'artist': all
            }

            tracks.append(track_data)
        
        return render_template('tracks.html', tracks=tracks)
    
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return redirect('/login')    
    
 
@app.route('/playlists')
def get_playlists():
    if 'access_token' not in session:
        return redirect('/login')
    
    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')
    
    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }
    
    response = requests.get(API_BASE_URL + '/me/playlists', headers=headers)
    response_data = json.loads(response.text)
    
    playlists = []
    for playlist in response_data['items']:
        name = playlist['name']
        creator = playlist['owner']['display_name']
        description = playlist['description']
        
        playlists.append({'name': name, 'creator': creator, 'description': description})

    return render_template('playlists.html', playlists=playlists)

def build_recommendations_url(params):
    """This function is used to help build the url 
        for the two pages that encoding the4 parameters that they use
        Input: dictionary (parameters)
        Output: str (url used to send requests)"""
    base_url = f"{API_BASE_URL}/recommendations"
    query_params = urllib.parse.urlencode(params)
    url = f"{base_url}?{query_params}"
    return url

@app.route('/suggestions', methods=['GET', 'POST'])
def get_song_suggestions():
    """This function runs the suggestions.html page"""
    if 'access_token' not in session:
        return redirect('/login')
    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')

    headers = {
        'Authorization': f"Bearer {session['access_token']}",
        #'Content-Type': 'application/json'
    }

    # Set the parameter values manually
    seed_artists = "5ficpwpxT4Gz9OsA3h3fFA"
    seed_genres = "work-out"
    limit = 15
    market = "US"

    params = {
        "seed_artists": seed_artists,
        "seed_genres": seed_genres,
        "limit": limit,
        "market": market
    }
    
    #build the url 
    url = build_recommendations_url(params)
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        response_data = response.json()
        suggestions = [] # make a list called suggestions to store all needed data
        for item in response_data['tracks']: # grab song name, popularity, and artist of each song
            song = item['name']
            artist = item['artists'][0]['name']
            popularity = item['popularity']
            
            # in the list of suggestions, each entry will be a dictionary holding the 
            # useful three pieces of information about each song
            sug_data = {
                'name': song, 
                'artist': artist,
                'popularity': popularity
            }
            
            suggestions.append(sug_data)
        return render_template('suggestions.html', data=suggestions)
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return redirect('/login')

def get_artist_id(artist_name):
    """This function is used to get the spotify id of an artist based on the artist name
        Input : str (name of artist)
        Output: str (spotify ID associated with artist)"""
    # Make a request to the Spotify API to search for the artist
    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }
    search_url = f"{API_BASE_URL}/search?q={artist_name}&type=artist&market=US&limit=1&offset=0"
    print(f'search url: {search_url}')
    response = requests.get(search_url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        if data['artists']['items']: # if there is any results
            # Return the ID of the first artist in the search results
            return data['artists']['items'][0]['id']

    # If no artist is found or an error occurs, return None
    print(f"no artists found")
    return None

   
@app.route('/custom-recommendations', methods=['POST', 'GET'])
def get_custom_recommendations():
    """This function is used to get custom reccomendations 
    based on the input values filled in in the html page"""
    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }
    if request.method == 'POST':
        # Get form data
        artist_name = request.form['artist']
        selected_genres = request.form['genre']
        min_pop = request.form.get('minimum', 0, type=int)
        max_pop = request.form.get('maximum', 100, type=int)
        
        #   print(f'artist:{artist_name}')
        #   print(f'genre: {selected_genres}')
    
        # Get the Spotify ID for the artist name
        artist_id = get_artist_id(artist_name)
        #   print(artist_id)

        if artist_id:
            # Build parameters for recommendation request
            seed_artists = artist_id
            seed_genres = selected_genres
            limit = 15
            market = "US"
            params = {
                "seed_artists": seed_artists,
                "seed_genres": seed_genres,
                "limit": limit,
                "market": market, 
                "min_popularity": min_pop,
                "max_popularity": max_pop
            }
            print(f'Reccomendations with params: {params}')

            # Make recommendation request to Spotify API
            url = build_recommendations_url(params)
            response = requests.get(url, headers=headers)
            
            # Response Code of 200 means that the request was successful
            if response.status_code == 200:
                response_data = response.json()
                suggestions = []
                for item in response_data['tracks']:
                    song = item['name']
                    artist = item['artists'][0]['name']
                    popularity = item['popularity']
                    # in the list of suggestions, each entry will be a dictionary holding the 
                    # useful pieces of information about each song
                    sug_data = {
                        'name': song,
                        'artist': artist,
                        'popularity': popularity
                    }
                    suggestions.append(sug_data)
                #print(suggestions)
                return render_template('custom_recommendations.html', data=suggestions)
            else:
                print(f"Error: {response.status_code} - {response.text}")
                return jsonify({'error': 'An error occurred while fetching recommendations'}), 400


    return render_template('custom_recommendations.html')

@app.route('/get-recommendations', methods=['POST'])
def get_recommendations():
    if request.method == 'POST':
        try:
            artist_name = request.form['artist']
            selected_genres = request.form['genre']
            min_pop = request.form.get('minimum', 0, type=int)
            max_pop = request.form.get('maximum', 100, type=int)

            artist_id = get_artist_id(artist_name)

            if artist_id:
                seed_artists = artist_id
                seed_genres = selected_genres
                limit = 15
                market = "US"
                params = {
                    "seed_artists": seed_artists,
                    "seed_genres": seed_genres,
                    "limit": limit,
                    "market": market,
                    "min_popularity": min_pop,
                    "max_popularity": max_pop
                }

                url = build_recommendations_url(params)
                headers = {'Authorization': f"Bearer {session['access_token']}"}
                response = requests.get(url, headers=headers)

                if response.status_code == 200:
                    response_data = response.json()
                    suggestions = []
                    for item in response_data['tracks']:
                        song = item['name']
                        artist = item['artists'][0]['name']
                        popularity = item['popularity']
                        sug_data = {
                            'name': song,
                            'artist': artist,
                            'popularity': popularity
                        }
                        suggestions.append(sug_data)

                    return jsonify(suggestions)
                else:
                    print(f"Error: {response.status_code} - {response.text}")
                    return jsonify({'error': 'An error occurred while fetching recommendations'}), 400
            else:
                return jsonify({'error': 'No artist found'}), 404
        except Exception as e:
            print(f"Error: {e}")
            return jsonify({'error': 'An error occurred while processing the request'}), 500

    return jsonify({'error': 'Invalid request'}), 400

@app.route('/refresh-token')
def refresh_token():
    """This function is used to get a refresh token if our session is over (old one has expired)"""
    if 'refresh-token' not in session:
        return render_template('home_of_app.html')

    if datetime.now().timestamp() > session['expires_at']:
        # set the parameters for what has to be sent to get another token
        req_body = {
            'grant_type': 'refresh-token', 
            'refresh_token': session['refresh_token'], 
            'client_id': CLIENT_ID, 
            'client_secret': CLIENT_SECRET
        }
        # send this request with parameters and put the response in a json format
        response = request.post(TOKEN_URL, data=req_body)
        new_token_info = response.json()
        
        # save the new token and the date it expires at in the session
        session['access_token'] = new_token_info['access_token']
        session['expires_at'] =  datetime.now().timestamp() + new_token_info['expires_in']
        
        return redirect('/home')
    
    
    
if __name__ == '__main__':
    app.run(host ='0.0.0.0', debug=True)
        