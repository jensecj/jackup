from dataclasses import dataclass

import json

@dataclass
class Task:
    name: str
    source: str
    destination: str
    order: int

def toJSON(task: Task):
    return { 'name': task.name,
             'source': task.source,
             'destination': task.destination,
             'order': task.order }

def fromJSON(json) -> Task:
    return Task(json['name'], json['source'], json['destination'], int(json['order']))
