# This file is part of nightly-reporting-jobs.
#
# Developed for the LSST Data Management System.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

__all__ = [
    "get_day_obs",
    "query_exposures_without_visit_geometry",
]

import logging

import astropy
from astropy.time import Time, TimeDelta

logging.basicConfig(
    format="{levelname} {asctime} {name} - {message}",
    style="{",
)
_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


def get_start_end(day_obs):
    """Return start time and end time of a day_obs

    Parameters
    ----------
    day_obs : `str`
        day_obs in the format of YYYY-MM-DD.
    """
    start = Time(day_obs, scale="utc", format="isot") + TimeDelta(12 * 60 * 60, format="sec")
    end = start + TimeDelta(1, format="jd")
    return start, end


def get_day_obs(time: astropy.time.Time) -> int:
    """Convert a timestamp into a day-obs string.

    The day-obs is defined as the TAI date of an instant 12 hours before
    the timestamp.

    Parameters
    ----------
    time : `astropy.time.Time`
        The timestamp to convert.

    Returns
    -------
    day_obs : `int`
        The day_obs corresponding to ``time``, in YYYYMMDD format.
    """
    day_obs_delta = TimeDelta(-12.0 * astropy.units.hour, scale="tai")
    iso_date = (time + day_obs_delta).tai.to_value("iso", "date")
    return int(iso_date.replace("-", ""))


def query_exposures_without_visit_geometry(
    butler,
    survey,
    day_obs=None,
    time_start_tai=None,
    time_end_tai=None,
    collections=None,
):
    """Query exposures without visit_geometry from butler for a given day_obs
    and survey.

    Parameters
    ----------
    butler : `lsst.daf.butler.Butler`
        Butler instance for querying.
    survey : `str`
        Survey/science program name (e.g., "BLOCK-407").
    day_obs : `int`, optional
        Day of observation in YYYYMMDD format.
        If not provided, calculated from time_start_tai.
    time_start_tai : `str`, optional
        Start time in TAI format (e.g., "2026-03-31T00:08:02.994000").
        If not provided, calculated from day_obs.
    time_end_tai : `str`, optional
        End time in TAI format (e.g., "2026-03-31T05:48:02.994000").
        If not provided, calculated from day_obs.
    collections : `str` or `list` [`str`]
        A collection name or iterable of collection names to search for
        existing visit_geometry.

    Returns
    -------
    results : `list`
        A list of exposure IDs without visit_geometry.
    """

    # Step 1: Parse times as astropy Time objects, ensure TAI scale
    t_start = Time(time_start_tai, scale="tai") if time_start_tai else None
    t_end = Time(time_end_tai, scale="tai") if time_end_tai else None

    # Step 2: Determine day_obs if not given, using time_start_tai
    if day_obs is None:
        if t_start is None:
            raise ValueError("Either day_obs or time_start_tai must be provided")
        day_obs = get_day_obs(t_start)

    # Convert day_obs from integer YYYYMMDD to YYYY-MM-DD string format
    day_obs_str = f"{day_obs // 10000:04d}-{(day_obs // 100) % 100:02d}-{day_obs % 100:02d}"
    # Step 3: Get the nominal interval for the given day_obs
    day_obs_start_utc, day_obs_end_utc = get_start_end(day_obs_str)
    day_obs_start_tai = day_obs_start_utc.tai
    day_obs_end_tai = day_obs_end_utc.tai

    # Step 4: Fill in missing time_start_tai, time_end_tai from day_obs
    if t_start is None:
        t_start = day_obs_start_tai
        time_start_tai = t_start.isot
    if t_end is None:
        t_end = day_obs_end_tai
        time_end_tai = t_end.isot

    # Step 5: Consistency check -- do day_obs's interval and
    # [t_start, t_end] overlap?
    # If not, short-circuit and return empty list.
    latest_start = max(t_start, day_obs_start_tai)
    earliest_end = min(t_end, day_obs_end_tai)
    if latest_start >= earliest_end:
        _log.warning("No overlap in time window & day_obs")
        return []

    results = butler.query_dimension_records(
        "exposure",
        where="exposure.science_program IN (survey) "
        "and instrument=instrument_name and day_obs=day_obs "
        f"and exposure.timespan.end > T'{time_start_tai}' "
        f"and exposure.timespan.end < T'{time_end_tai}'",
        bind={"day_obs": day_obs, "instrument_name": "LSSTCam", "survey": survey},
        explain=False,
        limit=None,
    )

    exposures = {exposure.id for exposure in results}
    exposure_exists = set()
    if collections:
        exists = butler.query_datasets(
            "visit_geometry",
            collections=collections,
            find_first=False,
            where="instrument='LSSTCam' and exposure in (exposures)",
            bind={"exposures": exposures},
            explain=False,
            limit=None,
        )
        exposure_exists = {_.dataId["visit"] for _ in exists}
    return list(exposures - exposure_exists)
