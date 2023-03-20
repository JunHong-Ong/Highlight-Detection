import requests
import time
import emoji

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)

bp = Blueprint("api", __name__)

class API():

    def __init__(self) -> None:
        self._headers = {"Client-Id":"kimne78kx3ncx6brgo4mv6wki5h1ko"}
        self._data = {
            "operationName":"VideoCommentsByOffsetOrCursor",
            "variables":{
                "contentOffsetSeconds":0
            },
            "extensions":{
                "persistedQuery":{
                    "version":1,
                    "sha256Hash":"b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"
                }
            }
        }

    @property
    def data(self):
        return self._data
    
    @data.setter
    def data(self, video_id):
        self._data["variables"]["videoID"] = str(video_id)

    def update_cursor(self, cursor) -> None:
        if cursor == None:
            return

        self.data["variables"].update({"cursor":cursor})

        if "contentOffsetSeconds" in self.data["variables"].keys():
            self.data["variables"].pop("contentOffsetSeconds")

    def get_comments(self, id):
        self.data = id

        while True:
            self.response = requests.post("https://gql.twitch.tv/gql", headers=self._headers, json=self._data).json()
            hasPagination = self.response["data"]["video"]["comments"]["pageInfo"]["hasNextPage"]
            self.cursor = self.response["data"]["video"]["comments"]["edges"][-1]["cursor"]
            comments = self.response["data"]["video"]["comments"]["edges"]

            for comment in comments:
                yield Comment(comment["node"]) 

            self.update_cursor(self.cursor)

            time.sleep(0.2)
            
            if not hasPagination:
                return

class User():

    def __init__(self, data) -> None:
        self.data = data

        # self.id = data.get("id")
        self.name = str(data.get("displayName")) if self.data != None else "None"

class Message():

    def __init__(self, data) -> None:
        self.data = data

        self.fragments = [Fragment(fragment) for fragment in self.data.get("fragments", [])]

class Fragment():

    def __init__(self, data) -> None:
        self.data = data
        self.type = "text" if self.data.get("emote") == None else "emote"

        # self.message = "".join([" E" if emoji.is_emoji(i) else i for i in self.data.get("text")]) if self.type == "text" else "E"
        self.message = self.data.get("text")

class Comment():

    def __init__(self, data) -> None:
        self.data = data

        self.id = self.data.get("id")
        self.commenter = User(self.data.get("commenter", {}))
        self.offsetSec = int(self.data.get("contentOffsetSeconds"))
        self.createdAt = self.data.get("createdAt")
        self.message = Message(self.data.get("message"))


    def text(self):
        return "".join([fragment.message for fragment in self.message.fragments])

    def words(self):
        message = "".join([fragment.message for fragment in self.message.fragments if fragment.type == "text"])
        message = "".join([i for i in message if not emoji.is_emoji(i)])
        return message

    def countEmotes(self):
        return int(sum([1 if fragment.type == "emote" else sum([emoji.is_emoji(i) for i in fragment.message]) for fragment in self.message.fragments]))
