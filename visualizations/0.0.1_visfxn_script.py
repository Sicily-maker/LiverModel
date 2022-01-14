# -*- coding: utf-8 -*-
r"""Contains functions for visualizing time profiles of simulation results.

This module contains the following functions for visualization of
time-dependent solutions returned in :class:`~.MassSolution`\ s after
simulation of models.

    * :func:`~.time_profiles.plot_time_profile`

"""
from warnings import warn
import altair as alt
from six import iteritems