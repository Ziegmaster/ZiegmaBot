import os
import dotenv
import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from ytmusicapi import YTMusic
from urllib.parse import urlparse, parse_qs
from isoduration import parse_duration

dotenv.load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'
API_KEY = os.environ['YOUTUBE_API_KEY']

def time_convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return '%d:%02d:%02d' % (hour, minutes, seconds) if hour > 0 else '%02d:%02d' % (minutes, seconds)

def parse_url(query : str, platform : int):
    allowed_hosts = ['www.youtube.com', 'youtube.com', 'm.youtube.com', 'music.youtube.com']
    query = urlparse(query)
    result = {
        'id' : None,
        'platform' : platform
    }
    if query.hostname == 'youtu.be': result['id'] = query.path[1:]
    if query.hostname == allowed_hosts[3]: result['platform'] = 1
    if query.hostname in allowed_hosts:
        if query.path == '/watch': result['id'] = parse_qs(query.query)['v'][0]
        elif query.path[:7] == '/watch/': result['id'] = query.path.split('/')[1]
        elif query.path[:7] == '/embed/': result['id'] = query.path.split('/')[2]
        elif query.path[:3] == '/v/': result['id'] = query.path.split('/')[2]
    return result

class YouTubeSearchClient:

    youtube = build(serviceName=API_SERVICE_NAME, version=API_VERSION, developerKey=API_KEY)
    ytmusic = YTMusic()

    def get_video_by_id(self, id : str):
        if id:
            request = self.youtube.videos().list(part='snippet,status,contentDetails', id=id)
            response = request.execute()
            if len(response['items']) > 0:
                video_meta = response['items'][0]
                if video_meta['status']['embeddable'] == True:
                    time_duration = parse_duration(video_meta['contentDetails']['duration']).time
                    duration_seconds = int(time_duration.hours) * 3600 + int(time_duration.minutes) * 60 + int(time_duration.seconds)
                    return {
                        'id' : id,
                        'url' : f'https://www.youtube.com/watch?v={id}',
                        'title' : video_meta['snippet']['title'],
                        'artists' : [{'name' : video_meta['snippet']['channelTitle']}],
                        'thumbnail' : video_meta['snippet']['thumbnails']['high']['url'],
                        'duration' : time_convert(duration_seconds),
                        'duration_seconds' : duration_seconds
                    }
        return None

    def get_video_by_search(self, query : str):
        request = self.youtube.search().list(part='snippet', maxResults=1, q=query, type='video', videoEmbeddable='true')
        response = request.execute()
        if len(response['items']) > 0:
            return response['items'][0]['id']['videoId']
        return None

    def get_song_by_id(self, id : str):
        result = self.ytmusic.get_song(id)
        if result:
            duration_seconds = int(result['videoDetails']['lengthSeconds'])
            return {
                'id' : id,
                'url' : f'https://music.youtube.com/watch?v={id}',
                'title' : result['videoDetails']['title'],
                'artists' : [{'name' : result['videoDetails']['author']}],
                'thumbnail' : result['videoDetails']['thumbnail']['thumbnails'][1]['url'],
                'duration' : time_convert(duration_seconds),
                'duration_seconds' : duration_seconds
            }
        return None

    def get_song_by_search(self, query: str):
        result = self.ytmusic.search(query=query, filter='songs', limit=1)
        if len(result) > 0:
            return {
                'id' : result[0]['videoId'],
                'url' : f'https://music.youtube.com/watch?v={result[0]["videoId"]}',
                'title' : result[0]['title'],
                'artists' : result[0]['artists'],
                'thumbnail' : result[0]['thumbnails'][1]['url'],
                'duration' : result[0]['duration'],
                'duration_seconds' : result[0]['duration_seconds'],
            }

    def get_request(self, query : str, platform : int = 0):
        request_meta = parse_url(query, platform)
        if request_meta['platform'] == 0:
            return request_meta | (self.get_video_by_id(request_meta['id']) if request_meta['id'] else self.get_video_by_id(self.get_video_by_search(query)))
        else:
            return request_meta | (self.get_song_by_id(request_meta['id']) if request_meta['id'] else self.get_song_by_search(query))
