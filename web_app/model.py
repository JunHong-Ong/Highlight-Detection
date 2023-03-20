import os
import math
import functools
import pandas as pd
import tensorflow as tf
from tensorflow import keras

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)
from web_app.api import API

bp = Blueprint("model", __name__)

def build_model(d=128, t=5):

    lstm_input = keras.layers.Input(shape=(None, 4))
    lstm_1 = keras.layers.LSTM(d, input_shape=(None, 4), return_sequences=True)(
        lstm_input
    )
    output, state_h, state_c = keras.layers.LSTM(d, return_state=True)(
        lstm_1
    )
    h_bar = keras.layers.Average()(
        [state_h]
    )
    output = keras.layers.Dense(1, activation="sigmoid")(h_bar)

    model = keras.Model([lstm_input], output)
    model.compile(loss='binary_crossentropy', optimizer="SGD", metrics=["accuracy", "AUC"])

    model.load_weights(os.path.join(current_app.instance_path, "model_weights"))

    return model

def get_model():
    if "model" not in g:
        g.model = build_model()

    return g.model

def getFeatures(df, start, t=5):
    end = start + t
    df = df.loc[(df["offsetSec"]>=start)&(df["offsetSec"]<=end),:]
    xu = len(df)
    if xu == 0:
        return [0,0,0,0]
    
    xe = sum(df["numEmotes"]) / (len(" ".join(df["words"]).split(" ")) + sum(df["numEmotes"]))
    xp = len(df["user"].unique())
    xl = len(" ".join(df["words"])) + sum(df["numEmotes"])

    return [xu, xe, xp, xl]

def convertTimestamp(seconds):
    hours = seconds // 3600
    minutes = (seconds - (hours*3600)) // 60
    seconds = (seconds - (hours*3600) - (minutes*60))

    return f"{hours}h{minutes}m{seconds}s"


@bp.route("/predict", methods=("GET", "POST"))
def predict():
    vod_id = request.form["vod-id"]

    model = get_model()
    api = API()
    data = pd.DataFrame(columns=["videoId","offsetSec","user","message","words","numEmotes"])

    for comment in api.get_comments(vod_id):
        line = pd.DataFrame(
            [[vod_id, comment.offsetSec, comment.commenter.name, comment.text(), comment.words(), comment.countEmotes()]],
            columns=["videoId","offsetSec","user","message","words","numEmotes"]
        )
        data = pd.concat([data,line], ignore_index=True)

    L = data["offsetSec"].max()
    l = 30 # Clip length
    t = 5 # Time window
    X = pd.DataFrame()

    for a in range(math.ceil(L/10)):
        start = a * 10
        end = start + l

        subset = data.loc[(data["offsetSec"] >= start) & (data["offsetSec"] <= end), :]
        nbins = math.ceil(l / t)
        output = [getFeatures(subset, a*10+(i*5)) for i in range(nbins)]
        X = pd.concat([X,pd.DataFrame({"input":[output]})], ignore_index=True)

    scores = model.predict(tf.ragged.constant(X["input"].values))
    scores = [
        {
            "score": score[0],
            "start": convertTimestamp(index*10),
            "end": convertTimestamp(index*10+30)
        }
        for index, score in enumerate(scores) if score[0] >= 0.6
    ]
    scores = sorted(scores, key=lambda x: x["score"], reverse=True)

    return render_template("model/predict.html", scores=scores[:10], video_id=vod_id)
