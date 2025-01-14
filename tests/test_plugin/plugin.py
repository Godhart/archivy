#!/usr/bin/env python3
from random import randint

import click

from archivy import app
from archivy.db import layer


@click.group()
def test_plugin():
    pass


@test_plugin.command()
@click.argument("upper_bound")
def random_number(upper_bound):
    click.echo(randint(1, int(upper_bound)))


@test_plugin.command()
def get_random_dataobj_title():
    with app.app_context():
        dataobjs = layer().get_items(structured=False)
        click.echo(dataobjs[randint(0, len(dataobjs))]["title"])
