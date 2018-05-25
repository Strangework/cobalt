import flask
import os
import requests
import urllib.parse
import sqlite3


app = flask.Flask(__name__)

# Generate secret key for encrypting cookies and session data
app.secret_key = os.urandom(24)


# URLs and endpoints
SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/authorize'
SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'

# !! : Have this URI depend on release/debug
# AUTH_REDIRECT_URI = 'http://127.0.0.1:5000/callback'
AUTH_REDIRECT_URI = 'http://strangework.net/xee/callback'


# Spotify app information
SPOTIFY_CLIENT_ID = '1d94080f30a04f85a93a711d8596784b'
SPOTIFY_CLIENT_SECRET = 'c7894c618092493b9b352737987e2a21'


# Comment database file
XEE_COMMENTS_DB = 'xee.sqlite3'


@app.route('/')
def xee():
    # If an authentication token doesn't exist in this session, get one
    if 'access_token' not in flask.session:
        print('NO TOKEN!')
        auth_query_params = {
          'client_id': SPOTIFY_CLIENT_ID,
          'scope': 'playlist-read-collaborative',
          'response_type': 'code',
          'redirect_uri': AUTH_REDIRECT_URI
        }
        url_args_list = []
        for key, val in auth_query_params.items():
            url_args_list.append("{}={}".format(key, urllib.parse.quote(val)))
        url_args = "&".join(url_args_list)
        auth_url = "{}/?{}".format(SPOTIFY_AUTH_URL, url_args)
        return flask.redirect(auth_url)

    print('GOT A TOKEN!')
    # Build authorization header
    authorization_header = {
      "Authorization": "Bearer {}".format(flask.session['access_token'])
    }

    # Get user's collaborative playlists
    playlist_query_resp = requests.get(
      '{}/playlists'.format(flask.session['spotify_profile_url']),
      headers=authorization_header
    )
    playlist_query_data = playlist_query_resp.json()
    playlists = []
    for item in playlist_query_data['items']:
        if item['collaborative']:
            playlists.append({
              'name': item['name'],
              'id': item['id']
            })

    # !! : Have app_root be set from a configuration file
    return flask.render_template(
      'xee.html',
      app_root='/xee',
      spotify_name=flask.session['spotify_user_id'],
      playlists=playlists
    )


@app.route('/callback')
def xee_callback():
    # Pull authentication token from incoming request
    auth_token = flask.request.args['code']
    token_payload = {
      'grant_type': 'authorization_code',
      'code': auth_token,
      'redirect_uri': AUTH_REDIRECT_URI,
      'client_id': SPOTIFY_CLIENT_ID,
      'client_secret': SPOTIFY_CLIENT_SECRET
    }
    token_resp = requests.post(SPOTIFY_TOKEN_URL, data=token_payload)

    # Store access token in session data
    token_data = token_resp.json()
    flask.session['access_token'] = token_data['access_token']

    # Build authorization header
    authorization_header = {
      "Authorization": "Bearer {}".format(flask.session['access_token'])
    }

    # Get user information and store in session
    spotify_profile_url = 'https://api.spotify.com/v1/me'
    profile_resp = requests.get(
      spotify_profile_url,
      headers=authorization_header
    )
    profile_data = profile_resp.json()
    user_id = profile_data['id']

    # Store user's Spotify user ID in the session
    flask.session['spotify_user_id'] = user_id
    flask.session['spotify_profile_url'] = profile_data['href']

    return flask.redirect(flask.url_for('xee'))


# Returns an array of tracks in the structure below
# [
# {
#   "title":"",
#   "artist":"",
#   "art_url":"",
#   "id":""
# }
# ]
@app.route('/playlist/<id>')
def get_playlist(id):
    # Build authorization header
    authorization_header = {
      "Authorization": "Bearer {}".format(flask.session['access_token'])
    }

    # Get playlist object
    playlist_url = 'https://api.spotify.com/v1/users/{0}/playlists/{1}'.format(flask.session['spotify_user_id'],id)
    playlist_resp = requests.get(playlist_url, headers=authorization_header)
    playlist_data = playlist_resp.json()
    print(playlist_data)

    tracks = []
    for track in playlist_data['tracks']['items']:
        curr_track = {}
        curr_track['title'] = track['track']['name']
        curr_track['artist'] = track['track']['artists'][0]['name']
        curr_track['art_url'] = track['track']['album']['images'][0]['url']
        curr_track['id'] = track['track']['id']
        tracks.append(curr_track)

    print(tracks)
    return(flask.jsonify(tracks))


# Returns an array of comments for the provided song in the structure below
# [
# {
#   "user":"",
#   "comment:"",
# }
# ]
@app.route('/song/<id>')
def get_song_comments(id):
    # Pull relevant comments from DB
    conn = sqlite3.connect(XEE_COMMENTS_DB)
    c = conn.cursor()
    c.execute('select * from comments where id=?', (id,))
    conn.commit()

    raw_comments = c.fetchall()
    comments = []
    for raw_comment in raw_comments:
        comment = {}
        comment['user'] = raw_comment[1]
        comment['comment'] = raw_comment[2]
        comments.append(comment)

    print(comments)

    return(flask.jsonify(comments))


# Accepts a JSON object describing a comment in the structure below
# {
#   "song_id":"",
#   "comment":""
# }
@app.route('/comment', methods=['POST'])
def write_comment():
    comment_obj = flask.request.get_json(force=True)
    # !! : Should check for login
    print(flask.session['spotify_user_id'])
    print(comment_obj)

    # Write comment to DB
    conn = sqlite3.connect(XEE_COMMENTS_DB)
    c = conn.cursor()
    params = (
      comment_obj['song_id'],
      flask.session['spotify_user_id'],
      comment_obj['comment']
    )
    c.execute('insert into comments values(?,?,?)', params)
    conn.commit()

    resp = {'ok': True}
    return flask.jsonify(resp)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
