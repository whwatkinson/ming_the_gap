from csv import DictReader
from dataclasses import dataclass
from typing import Union

from neomodel import config, db

from settings.environment_variables import NEO4J_DATABASE_URL

# from models.tube_lines import Piccadilly
from models.station import Station
from project_root import get_project_root

config.DATABASE_URL = NEO4J_DATABASE_URL


@dataclass
class TubeLine:
    line_name: str
    line_colour: str
    data_file_name: str


@dataclass
class TubeLineList:
    piccadilly = TubeLine("Piccadilly", "#1C1865", "piccadilly")


def load_connections(tube_line: TubeLine) -> None:
    print(f"Loading connections for {tube_line.line_name} line")

    with open(
        f"{get_project_root()}/data/connections/{tube_line.data_file_name}.csv",
        newline="\n",
    ) as csvfile:
        records = DictReader(csvfile, delimiter=",", quotechar='"')
        for row in records:

            res, _ = db.cypher_query(
                """
                MATCH (n:Station), (m:Station)
                WHERE $FROM IN n.tube_line_identifiers
                AND $TO IN m.tube_line_identifiers
                RETURN n, m;
                """,
                {"FROM": row["from_station"], "TO": row["to_station"]},
                resolve_objects=True,
            )
            if not res:
                raise Exception(f"No stations found for {row=}")

            from_station, to_station = res[0]

            if from_station.piccadilly.is_connected(to_station):
                continue

            from_station.piccadilly.connect(
                to_station,
                {
                    "line_name": "Piccadilly",
                    "line_colour": "#1C1865",
                    "forward_travel": row["forward_travel"] == "True",
                    "travel_time_seconds": float(row["travel_time_seconds"]),
                    "distance_km": float(row["distance_km"]),
                },
            )
    print(f"Loaded connections for {tube_line.line_name} line")


def load_tube_stations(tube_line: TubeLine) -> None:

    print(f"Loading stations for {tube_line.line_name} line")

    with open(
        f"{get_project_root()}/data/lines/{tube_line.data_file_name}.csv",
        newline="\n",
    ) as csvfile:
        records = DictReader(csvfile, delimiter=",", quotechar='"')
        for row in records:

            if station := Station.nodes.get_or_none(
                station_identifier=row["station_identifier"]
            ):
                station.update_tube_lines(tube_line.line_name)
                station.update_tube_line_identifiers(row["tube_line_identifier"])
                station.save()
            else:
                Station(
                    station_name=row["station_name"],
                    end_of_line=row["end_of_line"] == "True",
                    tube_lines=[tube_line.line_name],
                    tube_line_identifiers=[row["tube_line_identifier"]],
                    station_identifier=row["station_identifier"],
                    location=row["location"],
                    year_opened=int(row["year_opened"]) if row["year_opened"] else 0,
                    wiggle_ranking=row["wiggle_ranking"],
                ).save()
    print(f"Loaded stations for {tube_line.line_name} line")


def load_tube_lines() -> None:
    tll = TubeLineList()
    load_tube_stations(tll.piccadilly)
    load_connections(tll.piccadilly)


if __name__ == "__main__":
    db.cypher_query("MATCH (n) DETACH DELETE n;")
    load_tube_lines()
