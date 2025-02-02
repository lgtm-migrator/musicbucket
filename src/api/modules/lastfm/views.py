import pylast
from django.http import HttpResponse
from rest_framework import generics
from rest_framework.generics import get_object_or_404
from rest_framework import mixins as rf_mixins

from api.modules.lastfm.client import LastfmClient
from api.modules.lastfm.serializers import (
    NowPlayingSerializer,
    LastfmUserSerializer,
    TopAlbumsSerializer,
    TopArtistsSerializer,
    TopTracksSerializer,
)
from lastfm.models import LastfmUser
from spotify.client import SpotifyClient
from spotify.models import SpotifyLink
from telegram.models import TelegramUser


class NowPlayingAPIView(generics.RetrieveAPIView):
    serializer_class = NowPlayingSerializer
    http_method_names = ["get"]

    def get_object(self):
        telegram_user = get_object_or_404(
            TelegramUser, telegram_id=self.kwargs.get("user__telegram_id")
        )
        now_playing_data = None
        try:
            lastfm_user = telegram_user.lastfm_user
            now_playing_data = LastfmClient().now_playing(lastfm_user.username)
        except LastfmUser.DoesNotExist:
            lastfm_user = None

        data = {"is_playing_now": False, "lastfm_user": lastfm_user}
        if now_playing_data:
            data.update(
                {
                    "is_playing_now": True,
                    "artist_name": now_playing_data.get("artist").name
                    if now_playing_data.get("artist")
                    else None,
                    "album_name": now_playing_data.get("album").title
                    if now_playing_data.get("album")
                    else None,
                    "track_name": now_playing_data.get("track").title
                    if now_playing_data.get("track")
                    else None,
                    "cover": now_playing_data.get("cover"),
                    "url_candidate": self._search_for_candidate_spotify_url(
                        now_playing_data
                    ),
                }
            )
        return data

    @staticmethod
    def _search_for_candidate_spotify_url(now_playing_data: {}) -> str:
        spotify_client = SpotifyClient()
        album = now_playing_data.get("album")
        track = now_playing_data.get("track")

        if album:
            results = spotify_client.search_links(album, SpotifyLink.TYPE_ALBUM)
        else:
            results = spotify_client.search_links(track, SpotifyLink.TYPE_TRACK)
        if results:
            candidate_url = results[0]["external_urls"]["spotify"]
            return candidate_url


class CollageAPIView(generics.GenericAPIView):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        # TODO: Parameter validation
        # TODO: Accept entity as parameter
        telegram_user = get_object_or_404(
            TelegramUser, telegram_id=self.kwargs.get("user__telegram_id")
        )
        lastfm_user = telegram_user.lastfm_user
        query_params = self.request.query_params.copy()
        image = LastfmClient.generate_collage(
            lastfm_user.username,
            period=query_params.get("period", pylast.PERIOD_7DAYS),
            rows=int(query_params.get("rows", 5)),
            cols=int(query_params.get("cols", 5)),
        )
        response = HttpResponse(content_type="image/png")
        image.save(response, format="png")
        return response


class TopAlbumsView(generics.RetrieveAPIView):
    serializer_class = TopAlbumsSerializer
    http_method_names = ["get"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_fm_client = LastfmClient()

    def get_object(self):
        telegram_user = get_object_or_404(
            TelegramUser, telegram_id=self.kwargs.get("user__telegram_id")
        )

        period = self.request.query_params.get("period")
        if period not in self.last_fm_client.PERIODS:
            period = pylast.PERIOD_7DAYS

        top_albums = []
        try:
            lastfm_user = telegram_user.lastfm_user
            top_albums = LastfmClient().get_top_albums(lastfm_user.username, period)
        except LastfmUser.DoesNotExist:
            lastfm_user = None
        top_albums_data = {
            "lastfm_user": lastfm_user,
            "top_albums": [
                {
                    "artist": item.item.artist.name,
                    "title": item.item.title,
                    "scrobbles": item.weight,
                }
                for item in top_albums
            ],
        }
        return top_albums_data


class TopArtistsView(generics.RetrieveAPIView):
    serializer_class = TopArtistsSerializer
    http_method_names = ["get"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_fm_client = LastfmClient()

    def get_object(self):
        telegram_user = get_object_or_404(
            TelegramUser, telegram_id=self.kwargs.get("user__telegram_id")
        )

        period = self.request.query_params.get("period")
        if period not in self.last_fm_client.PERIODS:
            period = pylast.PERIOD_7DAYS

        top_artists = []
        try:
            lastfm_user = telegram_user.lastfm_user
            top_artists = self.last_fm_client.get_top_artists(lastfm_user.username, period)
        except LastfmUser.DoesNotExist:
            lastfm_user = None
        top_artists_data = {
            "lastfm_user": lastfm_user,
            "top_artists": [
                {"name": item.item.name, "scrobbles": item.weight}
                for item in top_artists
            ],
        }
        return top_artists_data


class TopTracksView(generics.RetrieveAPIView):
    serializer_class = TopTracksSerializer
    http_method_names = ["get"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_fm_client = LastfmClient()

    def get_object(self):
        telegram_user = get_object_or_404(
            TelegramUser, telegram_id=self.kwargs.get("user__telegram_id")
        )

        period = self.request.query_params.get("period")
        if period not in self.last_fm_client.PERIODS:
            period = pylast.PERIOD_7DAYS

        top_tracks = []
        try:
            lastfm_user = telegram_user.lastfm_user
            top_tracks = LastfmClient().get_top_tracks(lastfm_user.username, period)
        except LastfmUser.DoesNotExist:
            lastfm_user = None
        top_tracks_data = {
            "lastfm_user": lastfm_user,
            "top_tracks": [
                {
                    "artist": item.item.artist.name,
                    "title": item.item.title,
                    "scrobbles": item.weight,
                }
                for item in top_tracks
            ],
        }
        return top_tracks_data


class LastfmUserCreateUpdateAPIView(rf_mixins.UpdateModelMixin, generics.CreateAPIView):
    """
    This view is slightly different from the others.
    It only allows to create a Last.fm User if it already exists.
    Otherwise, updates it.
    """

    serializer_class = LastfmUserSerializer

    def post(self, request, *args, **kwargs):
        if LastfmUser.objects.filter(user_id=request.data.get("user_id")).exists():
            return self.update(request, *args, **kwargs)
        return self.create(request, *args, **kwargs)

    def get_queryset(self):
        lastfm_user = LastfmUser.objects.filter(
            user_id=self.request.data.get("user_id")
        )
        return lastfm_user

    def get_object(self):
        return LastfmUser.objects.get(user_id=self.request.data.get("user_id"))
