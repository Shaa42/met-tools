import glob
import json
from datetime import datetime, timedelta, timezone
from pprint import pprint

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from typing_extensions import List


def parse_json(args: List[str], json_dir: str = "data"):
    json_files = glob.glob(f"{json_dir}/*.json")
    json_dict = {}
    for file in json_files:
        with open(file, "r") as f:
            data = json.load(f)
            for arg in args:
                if json_dict.get(arg, 0):
                    json_dict[arg].append(data[arg])
                else:
                    json_dict[arg] = [data[arg]]
    return json_dict


def graph_data(json_dict: dict, key: str):
    x = [i for i in [j.split("_")[0].strip("data/") for j in glob.glob("data/*.json")]]
    y = [i for i in json_dict[key]]
    plt.plot(x, y)
    tick_indices = sorted(
        set([0, len(json_dict[key]) - 1] + list(range(0, len(json_dict[key]), 25)))
    )
    tick_positions = [x[i] for i in tick_indices]
    tz_plus_1 = timezone(timedelta(hours=1))
    tick_labels = [
        datetime.fromtimestamp(int(pos), tz=tz_plus_1).strftime("%H:%M")
        for pos in tick_positions
    ]
    plt.xticks(tick_positions, tick_labels)
    plt.xlabel("Heures et minutes à laquelle la page a été chargée")
    plt.ylabel("Temps total pour charger la page (s)")
    plt.title("Temps total pour charger une page fandom")
    plt.grid()
    plt.savefig("./graph.png")
    # plt.show()


if __name__ == "__main__":
    json_dict = parse_json(["total_time"])
    # pprint(json_dict, depth=1)
    graph_data(json_dict, "total_time")
