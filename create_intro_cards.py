from datetime import datetime
import glob
import logging
import os
import re
from typing import TypedDict, cast

import matplotlib as mpl
from matplotlib import axes
from matplotlib.text import Text
from matplotlib.transforms import Transform
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image


class StatsDict(TypedDict):
    """Metadata about a given run of the intro card creation process."""

    number_of_cards_created: int
    """The total number of intro cards that were created."""

    number_of_cards_to_create: int
    """The number of people for whom cards needed to be generated."""

    people_with_photo_warnings: list[str]
    """The names of people whose photos could not be found or read."""


# Required for ``make_pdf_preview``; matches Agg backend of `savefig` in `make_pdf`
mpl.use("module://matplotlib_inline.backend_inline")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def make_pdf(
    people_data: pd.DataFrame,
    first_name_col: str,
    last_name_col: str,
    photo_path_col: str,
    path_to_default_photo: str,
    path_to_output_dir: str = "./intro_cards_output",
    figure_size: tuple[float, float] = (23, 13),
    name_x_coord: float = 0.35,
    name_y_coord: float = 0.95,
    name_font_size: float = 50,
    desc_padding: float = 0.05,
    desc_font_size: float = 16,
    photo_axes_bounds: tuple[float, float, float, float] = (0.02, 0.02, 0.3, 0.93),
) -> StatsDict:
    """Generate a PDF containing intro cards for all individuals in ``people_data``.

    This is entrypoint of the module. It generates a PDF, where each page of the PDF is
    a single Matplotlib figure, which is itself composed of four individuals' intro
    cards. Each intro card contains an individual's name, their photo (either provided
    or default), and a description that displays their "column name: attribute value"
    pairings for each column in ``people_data`` (except ones related to their name and
    their photo path).

    On each intro card, "column name: attribute value" pairings are separated by a new
    line, and each "column name" is rendered in bold. Text on any given line is wrapped
    such that it approaches -- but does not touch -- the right border of the card. If an
    individual's "attribute value" is left blank, that particular "column name:
    attribute value" pairing will be omitted from their card. This function also
    provides parameters to tweak the formatting and layout of all individuals' intro
    cards, such as ``name_x_coord``, ``desc_padding`, and ``photo_axes_bounds``. Using
    :func:``make_pdf_preview`` (Jupyter environment required) allows for quick feedback
    on how these parameters affect the cards.

    The output PDF is saved down in ``path_to_output_dir``. Also in this directory are
    the constituent pages of the PDF (PNG images of the Matplotlib figures, as rendered
    using the Agg backend) and a logging file that denotes the names and photo
    availability statuses of all the individuals who had an intro card created.
    Depending on the number of individuals, the file size of the PDF might be quite
    large; to reduce it (at the expense of resolution), scale down each number in
    ``figure_size``, ``name_font_size``, and ``desc_font_size`` by a common factor.

    The function returns a dictionary with metadata pertaining to the number of intro
    cards that were created, the number of people for whom cards needed to be generated,
    and the names of people whose photos could not be found or read.

    :param people_data: The pandas DataFrame containing all the data from which to make
        intro cards. Rows represent individuals, while columns represent attributes of
        those individuals. The choice of attributes is completely up to the user (e.g.,
        "Hometown", "Fun Fact"), but it is required that there be columns for first
        name, last name, and paths to individuals' photos (which will ultimately be
        displayed on their respective intro cards). The name of each column -- except
        the ones for first name, last name, and photo paths -- will ultimately end up
        being listed on individuals' intro cards in bold. The order of these columns
        dictates the order in which "column name: attribute value" pairings are
        displayed on the cards.
    :type people_data: pd.DataFrame
    :param first_name_col: The name of the column (Series) in ``people_data`` that
        houses first names
    :type first_name_col: str
    :param last_name_col: The name of the column (Series) in ``people_data`` that houses
        last names
    :type last_name_col: str
    :param photo_path_col: The name of the column (Series) in ``people_data`` that
        houses paths to individuals' photos. The photos must be of a type that Pillow
        supports (e.g., PNG, JPG). Paths can be relative or absolute.
    :type photo_path_col: str
    :param path_to_default_photo: The path to the photo to use if an individual does not
        have a photo path listed ``people_data``. This default photo will also be used
        if there is indeed a photo path specified but the photo cannot be found at that
        location. The photo must be of a type that Pillow supports (e.g., PNG, JPG). If
        specifying this argument using a single-backlash separator, make sure to use a
        raw string.
    :type path_to_default_photo: str
    :param path_to_output_dir: The path to the output directory to use. The output
        directory will store the final PDF, its constituent pages/Matplob figures, and
        the logging file. If it does not exist, it will be created at runtime. If
        specifying this argument using a single-backlash separator, make sure to use a
        raw string., defaults to 'intro_cards_output'
    :type path_to_output_dir: str, optional
    :param figure_size: The size of the figure that Matplotlib will create when plotting
        a batch of four intro cards on it. The first entry in this tuple is the width of
        the figure and the second is the height (both in inches). Each figure will
        ultimately become its own page in the PDF., defaults to (23, 13)
    :type figure_size: tuple[float, float], optional
    :param name_x_coord: The (Axes-relative) x-coordinate of individuals' names on their
        intro cards (which are Matplotlib Axes). This will also be the x-coordinate of
        individuals' descriptions., defaults to 0.35
    :type name_x_coord: float, optional
    :param name_y_coord: The (Axes-relative) y-coordinate of individuals' names on their
        intro cards (which are Matplotlib Axes), defaults to 0.95
    :type name_y_coord: float, optional
    :param name_font_size: The font size of individuals' names on their intro cards,
        defaults to 50
    :type name_font_size: float, optional
    :param desc_padding: The amount of padding (in Axes-relative coordinates) below the
        lower bound of the name's bounding box, after which to begin plotting the
        individual's description, defaults to 0.05
    :type desc_padding: float, optional
    :param desc_font_size: The font size of individuals' descriptions on their intro
        cards. If this font size would cause the lower bound of the description's
        bounding box to come within 0.02 of the bottom of any individual's intro card
        (or even exceed it and be cut off), then this font size will be iteratively
        reduced by 5% on that specific intro card until this is no longer the case.,
        defaults to 16
    :type desc_font_size: float, optional
    :param photo_axes_bounds: The bounds of the photo Axes on individuals' intro cards
        (the photo Axes is inset within the main intro card Axes). The bounds should be
        given as (x0, y0, width, height), where x0 and y0 represent the lower-left
        corner of the photo Axes. The photo will ultimately grow from the upper-left
        corner of this bounding box with a fixed aspect ratio. All coordinates are Axes-
        relative., defaults to (0.02, 0.02, 0.3, 0.93)
    :type photo_axes_bounds: tuple[float, float, float, float], optional
    :raises OSError: If the default photo does not exist at the specified path, or if
        the default photo cannot be read by PIL, or if the specified output directory
        does not exist and then cannot be created
    :raises ValueError: If ``first_name_col``, ``last_name_col``, or ``photo_path_col``
        cannot be found in ``people_data``
    :return: Metadata pertaining to the number of intro cards that were created, the
        number of people for whom cards needed to be generated, and the names of people
        whose photos could not be found or read
    :rtype: StatsDict
    """
    if not os.path.exists(path_to_default_photo):
        raise OSError(
            "No photo exists at the specified default photo path. "
            "Please specify a valid path."
        )

    try:
        img = Image.open(path_to_default_photo)
        img.close()
    except OSError:
        raise OSError(
            f"Could not read the default photo at `{path_to_default_photo}`. "
            "Make sure the photo is of a format supported by PIL."
        )

    if not os.path.exists(path_to_output_dir):
        try:
            os.makedirs(path_to_output_dir)
        except OSError:
            raise OSError(f"Failed to create `{path_to_output_dir}` directory.")

    missing_columns = [
        col
        for col in [first_name_col, last_name_col, photo_path_col]
        if col not in people_data.columns
    ]
    if missing_columns:
        raise ValueError(
            "The following columns are not in `people_data`: "
            f"{', '.join(missing_columns)}. Please specify valid column names."
        )

    logger_stream_handler = logging.StreamHandler()
    logger_stream_formatter = logging.Formatter("%(message)s")
    logger_stream_handler.setFormatter(logger_stream_formatter)
    logger.addHandler(logger_stream_handler)

    local_timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    logger_file_handler = logging.FileHandler(
        os.path.join(path_to_output_dir, f"names_{local_timestamp}.log"), mode="w"
    )
    logger_file_formatter = logging.Formatter("%(message)s")
    logger_file_handler.setFormatter(logger_file_formatter)
    logger.addHandler(logger_file_handler)

    stats: StatsDict = {
        "number_of_cards_created": 0,
        "number_of_cards_to_create": people_data.shape[0],
        "people_with_photo_warnings": [],
    }

    try:
        _make_figs(
            people_data,
            first_name_col,
            last_name_col,
            photo_path_col,
            path_to_default_photo,
            path_to_output_dir,
            figure_size,
            name_x_coord,
            name_y_coord,
            name_font_size,
            desc_padding,
            desc_font_size,
            photo_axes_bounds,
            stats=stats,
        )
        figure_image_paths = glob.glob(os.path.join(path_to_output_dir, "*.png"))
        sorted_figure_image_paths = sorted(
            figure_image_paths,
            key=lambda x: int(
                cast(re.Match[str], re.search(r"figure(\d+)\.png", x)).group(1)
            ),
        )
        first_img = Image.open(sorted_figure_image_paths[0])
        first_img.save(
            os.path.join(path_to_output_dir, "intro_cards.pdf"),
            # dpi; same value as in plt.subplots() so inch dimensions are preserved
            resolution=175,
            save_all=True,
            append_images=(Image.open(path) for path in sorted_figure_image_paths[1:]),
        )
        plt.close(fig="all")

        logger.info(
            f"\n\nComplete! See the directory `{path_to_output_dir}` for the PDF."
        )
        if stats["people_with_photo_warnings"]:
            logger.info(
                "\nWARNING: Photos could not be found or read at the specified paths "
                "for the name(s) below. Please confirm the path(s) are valid and that "
                "the photo(s) are of a format supported by PIL.\n"
            )
            logger.info("\n".join(stats["people_with_photo_warnings"]))
        return stats
    except Exception as e:
        logger.error(e)
        raise
    finally:
        logger.removeHandler(logger_stream_handler)
        logger_file_handler.close()
        logger.removeHandler(logger_file_handler)


def make_pdf_preview(
    people_data: pd.DataFrame,
    first_name_col: str,
    last_name_col: str,
    photo_path_col: str,
    path_to_default_photo: str,
    figure_size: tuple[float, float] = (23, 13),
    name_x_coord: float = 0.35,
    name_y_coord: float = 0.95,
    name_font_size: float = 50,
    desc_padding: float = 0.05,
    desc_font_size: float = 16,
    photo_axes_bounds: tuple[float, float, float, float] = (0.02, 0.02, 0.3, 0.93),
) -> StatsDict:
    """Show a preview in a Jupyter environment of the first page of the PDF that would
    be created if :func:`make_pdf` were run, and print logging output to the console.

    This function is helpful to gauge how the output will look in response to tweaking
    certain parameters (e.g., ``name_font_size``) without having to actually iterate
    through the entirety of ``people_data`` and compile the PDF. Its parameters,
    defaults, and return type are identical to those of :func:`make_pdf`, except for its
    omission of ``path_to_output_dir``. It serves primarily as a wrapper for
    :func:`_make_fig_preview` to allow for more consistent naming in the public API.

    Because this function uses Matplotlib's inline backend, it is required to be run in
    a Jupyter environment. The figures displayed by this backend ultimately match those
    that are rendered by the Agg backend that is implicitly used in each of
    :func:`make_pdf`'s :func:`fig.savefig` calls.

    :param people_data: The pandas DataFrame containing all the data from which to make
        intro cards. Rows represent individuals, while columns represent attributes of
        those individuals. The choice of attributes is completely up to the user (e.g.,
        "Hometown", "Fun Fact"), but it is required that there be columns for first
        name, last name, and paths to individuals' photos (which will ultimately be
        displayed on their respective intro cards). The name of each column -- except
        the ones for first name, last name, and photo paths -- will ultimately end up
        being listed on individuals' intro cards in bold. The order of these columns
        dictates the order in which "column name: attribute value" pairings are
        displayed on the cards.
    :type people_data: pd.DataFrame
    :param first_name_col: The name of the column (Series) in ``people_data`` that
        houses first names
    :type first_name_col: str
    :param last_name_col: The name of the column (Series) in ``people_data`` that houses
        last names
    :type last_name_col: str
    :param photo_path_col: The name of the column (Series) in ``people_data`` that
        houses paths to individuals' photos. The photos must be of a type that Pillow
        supports (e.g., PNG, JPG). Paths can be relative or absolute.
    :type photo_path_col: str
    :param path_to_default_photo: The path to the photo to use if an individual does not
        have a photo path listed ``people_data``. This default photo will also be used
        if there is indeed a photo path specified but the photo cannot be found at that
        location. The photo must be of a type that Pillow supports (e.g., PNG, JPG). If
        specifying this argument using a single-backlash separator, make sure to use a
        raw string.
    :type path_to_default_photo: str
    :param figure_size: The size of the figure that Matplotlib will create when plotting
        a batch of four intro cards on it. The first entry in this tuple is the width of
        the figure and the second is the height (both in inches). Each figure will
        ultimately become its own page in the PDF., defaults to (23, 13)
    :type figure_size: tuple[float, float], optional
    :param name_x_coord: The (Axes-relative) x-coordinate of individuals' names on their
        intro cards (which are Matplotlib Axes). This will also be the x-coordinate of
        individuals' descriptions., defaults to 0.35
    :type name_x_coord: float, optional
    :param name_y_coord: The (Axes-relative) y-coordinate of individuals' names on their
        intro cards (which are Matplotlib Axes), defaults to 0.95
    :type name_y_coord: float, optional
    :param name_font_size: The font size of individuals' names on their intro cards,
        defaults to 50
    :type name_font_size: float, optional
    :param desc_padding: The amount of padding (in Axes-relative coordinates) below the
        lower bound of the name's bounding box, after which to begin plotting the
        individual's description, defaults to 0.05
    :type desc_padding: float, optional
    :param desc_font_size: The font size of individuals' descriptions on their intro
        cards. If this font size would cause the lower bound of the description's
        bounding box to come within 0.02 of the bottom of any individual's intro card
        (or even exceed it and be cut off), then this font size will be iteratively
        reduced by 5% on that specific intro card until this is no longer the case.,
        defaults to 16
    :type desc_font_size: float, optional
    :param photo_axes_bounds: The bounds of the photo Axes on individuals' intro cards
        (the photo Axes is inset within the main intro card Axes). The bounds should be
        given as (x0, y0, width, height), where x0 and y0 represent the lower-left
        corner of the photo Axes. The photo will ultimately grow from the upper-left
        corner of this bounding box with a fixed aspect ratio. All coordinates are Axes-
        relative., defaults to (0.02, 0.02, 0.3, 0.93)
    :type photo_axes_bounds: tuple[float, float, float, float], optional
    :raises OSError: If the default photo does not exist at the specified path, or if
        the default photo cannot be read by PIL
    :raises ValueError: If ``first_name_col``, ``last_name_col``, or ``photo_path_col``
        cannot be found in ``people_data``
    :return: Metadata pertaining to the number of intro cards that were created, the
        number of people for whom cards needed to be generated, and the names of people
        whose photos could not be found or read
    :rtype: StatsDict
    """
    if not os.path.exists(path_to_default_photo):
        raise OSError(
            "No photo exists at the specified default photo path. "
            "Please specify a valid path."
        )

    try:
        img = Image.open(path_to_default_photo)
        img.close()
    except OSError:
        raise OSError(
            f"Could not read the default photo at `{path_to_default_photo}`. "
            "Make sure the photo is of a format supported by PIL."
        )

    missing_columns = [
        col
        for col in [first_name_col, last_name_col, photo_path_col]
        if col not in people_data.columns
    ]
    if missing_columns:
        raise ValueError(
            "The following columns are not in `people_data`: "
            f"{', '.join(missing_columns)}. Please specify valid column names."
        )

    logger_stream_handler = logging.StreamHandler()
    logger_stream_formatter = logging.Formatter("%(message)s")
    logger_stream_handler.setFormatter(logger_stream_formatter)
    logger.addHandler(logger_stream_handler)

    stats: StatsDict = {
        "number_of_cards_created": 0,
        "number_of_cards_to_create": min(people_data.shape[0], 4),
        "people_with_photo_warnings": [],
    }

    try:
        _make_fig_preview(
            people_data,
            first_name_col,
            last_name_col,
            photo_path_col,
            path_to_default_photo,
            figure_size,
            name_x_coord,
            name_y_coord,
            name_font_size,
            desc_padding,
            desc_font_size,
            photo_axes_bounds,
            stats=stats,
        )

        if stats["people_with_photo_warnings"]:
            logger.info(
                "WARNING: Photos could not be found at the specified paths "
                "for the name(s) below. Please confirm the photo path(s).\n"
            )
            logger.info("\n".join(stats["people_with_photo_warnings"]))
        return stats
    except Exception as e:
        logger.error(e)
        raise
    finally:
        logger.removeHandler(logger_stream_handler)


def _make_figs(
    people_data: pd.DataFrame,
    first_name_col: str,
    last_name_col: str,
    photo_path_col: str,
    path_to_default_photo: str,
    path_to_output_dir: str,
    figure_size: tuple[float, float],
    name_x_coord: float,
    name_y_coord: float,
    name_font_size: float,
    desc_padding: float,
    desc_font_size: float,
    photo_axes_bounds: tuple[float, float, float, float],
    stats: StatsDict,
) -> None:
    """Iteratively grab batches of four rows (individuals) from ``people_data``, and for
    each batch save a Matplotlib figure that shows those four individuals' intro cards.
    Private function.

    All figures will be saved as PNG files in ``path_to_output_dir``. If the number of
    rows in ``people_data`` is not divisible by 4, the last figure will show only as
    many individuals are needed to account for every individual in the DataFrame.

    :param people_data: The pandas DataFrame containing all the data from which to make
        intro cards. Rows represent individuals, while columns represent attributes of
        those individuals. The choice of attributes is completely up to the user (e.g.,
        "Hometown", "Fun Fact"), but it is required that there be columns for first
        name, last name, and paths to individuals' photos (which will ultimately be
        displayed on their respective intro cards). The name of each column -- except
        the ones for first name, last name, and photo paths -- will ultimately end up
        being listed on individuals' intro cards in bold. The order of these columns
        dictates the order in which "column name: attribute value" pairings are
        displayed on the cards.
    :type people_data: pd.DataFrame
    :param first_name_col: The name of the column (Series) in ``people_data`` that
        houses first names
    :type first_name_col: str
    :param last_name_col: The name of the column (Series) in ``people_data`` that houses
        last names
    :type last_name_col: str
    :param photo_path_col: The name of the column (Series) in ``people_data`` that
        houses paths to individuals' photos. The photos must be of a type that Pillow
        supports (e.g., PNG, JPG). Paths can be relative or absolute.
    :type photo_path_col: str
    :param path_to_default_photo: The path to the photo to use if an individual does not
        have a photo path listed ``people_data``. This default photo will also be used
        if there is indeed a photo path specified but the photo cannot be found at that
        location. The photo must be of a type that Pillow supports (e.g., PNG, JPG). If
        specifying this argument using a single-backlash separator, make sure to use a
        raw string.
    :type path_to_default_photo: str
    :param path_to_output_dir: The path to the output directory to use. The output
        directory will store the final PDF, its constituent pages/Matplob figures, and
        the logging file. If it does not exist, it will be created at runtime. If
        specifying this argument using a single-backlash separator, make sure to use a
        raw string.
    :type path_to_output_dir: str
    :param figure_size: The size of the figure that Matplotlib will create when plotting
        a batch of four intro cards on it. The first entry in this tuple is the width of
        the figure and the second is the height (both in inches). Each figure will
        ultimately become its own page in the PDF.
    :type figure_size: tuple[float, float]
    :param name_x_coord: The (Axes-relative) x-coordinate of individuals' names on their
        intro cards (which are Matplotlib Axes). This will also be the x-coordinate of
        individuals' descriptions.
    :type name_x_coord: float
    :param name_y_coord: The (Axes-relative) y-coordinate of individuals' names on their
        intro cards (which are Matplotlib Axes)
    :type name_y_coord: float
    :param name_font_size: The font size of individuals' names on their intro cards
    :type name_font_size: float
    :param desc_padding: The amount of padding (in Axes-relative coordinates) below the
        lower bound of the name's bounding box, after which to begin plotting the
        individual's description
    :type desc_padding: float
    :param desc_font_size: The font size of individuals' descriptions on their intro
        cards. If this font size would cause the lower bound of the description's
        bounding box to come within 0.02 of the bottom of any individual's intro card
        (or even exceed it and be cut off), then this font size will be iteratively
        reduced by 5% on that specific intro card until this is no longer the case.,
        defaults to 16
    :type desc_font_size: float
    :param photo_axes_bounds: The bounds of the photo Axes on individuals' intro cards
        (the photo Axes is inset within the main intro card Axes). The bounds should be
        given as (x0, y0, width, height), where x0 and y0 represent the lower-left
        corner of the photo Axes. The photo will ultimately grow from the upper-left
        corner of this bounding box with a fixed aspect ratio. All coordinates are Axes-
        relative.
    :type photo_axes_bounds: tuple[float, float, float, float]
    :param stats: Metadata pertaining to the number of intro cards that were created,
        the number of people for whom cards needed to be generated, and the names of
        people whose photos could not be found or read
    :type stats: StatsDict
    :return: None
    :rtype: NoneType
    """
    people_data = _format_data_and_derive_full_names(
        people_data, first_name_col, last_name_col, photo_path_col
    )

    with mpl.rc_context({"mathtext.default": "bf"}):
        start_ind = 0
        for i in np.arange(_ceil_div(people_data.shape[0], 4)):
            if start_ind + 4 <= people_data.shape[0]:
                end_ind = start_ind + 4
            else:
                end_ind = people_data.shape[0]
            fig, axs = plt.subplots(2, 2, figsize=figure_size, dpi=175)
            fig.tight_layout(h_pad=0.1, w_pad=0.1)
            for ax in axs.ravel():
                ax.axis("off")
            for row, ax in zip(
                people_data.iloc[start_ind:end_ind].iterrows(), axs.ravel()
            ):
                _make_card(
                    row[1],
                    ax,
                    first_name_col,
                    last_name_col,
                    photo_path_col,
                    path_to_default_photo,
                    name_x_coord,
                    name_y_coord,
                    name_font_size,
                    desc_padding,
                    desc_font_size,
                    photo_axes_bounds,
                    stats=stats,
                )
            fig.savefig(os.path.join(path_to_output_dir, f"figure{i + 1}.png"))
            start_ind += 4


def _make_fig_preview(
    people_data: pd.DataFrame,
    first_name_col: str,
    last_name_col: str,
    photo_path_col: str,
    path_to_default_photo: str,
    figure_size: tuple[float, float],
    name_x_coord: float,
    name_y_coord: float,
    name_font_size: float,
    desc_padding: float,
    desc_font_size: float,
    photo_axes_bounds: tuple[float, float, float, float],
    stats: StatsDict,
) -> None:
    """Show a preview (using `plt.show()`) of the first page of the PDF that would be
    created if :func:`make_pdf` were run. Private function.

    This function is called internally by ``make_pdf_preview`` to gauge how the output
    will look in response to tweaking certain parameters (e.g., ``name_font_size``),
    without having to iterate through the entirety of ``people_data``. Its parameters
    are identical to those of :func:`_make_figs`, except for its omission of
    ``path_to_output_dir``.

    :param people_data: The pandas DataFrame containing all the data from which to make
        intro cards. Rows represent individuals, while columns represent attributes of
        those individuals. The choice of attributes is completely up to the user (e.g.,
        "Hometown", "Fun Fact"), but it is required that there be columns for first
        name, last name, and paths to individuals' photos (which will ultimately be
        displayed on their respective intro cards). The name of each column -- except
        the ones for first name, last name, and photo paths -- will ultimately end up
        being listed on individuals' intro cards in bold. The order of these columns
        dictates the order in which "column name: attribute value" pairings are
        displayed on the cards.
    :type people_data: pd.DataFrame
    :param first_name_col: The name of the column (Series) in ``people_data`` that
        houses first names
    :type first_name_col: str
    :param last_name_col: The name of the column (Series) in ``people_data`` that houses
        last names
    :type last_name_col: str
    :param photo_path_col: The name of the column (Series) in ``people_data`` that
        houses paths to individuals' photos. The photos must be of a type that Pillow
        supports (e.g., PNG, JPG). Paths can be relative or absolute.
    :type photo_path_col: str
    :param path_to_default_photo: The path to the photo to use if an individual does not
        have a photo path listed ``people_data``. This default photo will also be used
        if there is indeed a photo path specified but the photo cannot be found at that
        location. The photo must be of a type that Pillow supports (e.g., PNG, JPG). If
        specifying this argument using a single-backlash separator, make sure to use a
        raw string.
    :type path_to_default_photo: str
    :param figure_size: The size of the figure that Matplotlib will create when plotting
        a batch of four intro cards on it. The first entry in this tuple is the width of
        the figure and the second is the height (both in inches). Each figure will
        ultimately become its own page in the PDF.
    :type figure_size: tuple[float, float]
    :param name_x_coord: The (Axes-relative) x-coordinate of individuals' names on their
        intro cards (which are Matplotlib Axes). This will also be the x-coordinate of
        individuals' descriptions.
    :type name_x_coord: float
    :param name_y_coord: The (Axes-relative) y-coordinate of individuals' names on their
        intro cards (which are Matplotlib Axes)
    :type name_y_coord: float
    :param name_font_size: The font size of individuals' names on their intro cards
    :type name_font_size: float
    :param desc_padding: The amount of padding (in Axes-relative coordinates) below the
        lower bound of the name's bounding box, after which to begin plotting the
        individual's description
    :type desc_padding: float
    :param desc_font_size: The font size of individuals' descriptions on their intro
        cards. If this font size would cause the lower bound of the description's
        bounding box to come within 0.02 of the bottom of any individual's intro card
        (or even exceed it and be cut off), then this font size will be iteratively
        reduced by 5% on that specific intro card until this is no longer the case.
    :type desc_font_size: float
    :param photo_axes_bounds: The bounds of the photo Axes on individuals' intro cards
        (the photo Axes is inset within the main intro card Axes). The bounds should be
        given as (x0, y0, width, height), where x0 and y0 represent the lower-left
        corner of the photo Axes. The photo will ultimately grow from the upper-left
        corner of this bounding box with a fixed aspect ratio. All coordinates are Axes-
        relative.
    :type photo_axes_bounds: tuple[float, float, float, float]
    :param stats: Metadata pertaining to the number of intro cards that were created,
        the number of people for whom cards needed to be generated, and the names of
        people whose photos could not be found or read
    :type stats: StatsDict
    :return: None
    :rtype: NoneType
    """
    people_data = _format_data_and_derive_full_names(
        people_data, first_name_col, last_name_col, photo_path_col
    )

    plt.close("all")

    with mpl.rc_context({"mathtext.default": "bf"}):
        end_ind = min(people_data.shape[0], 4)
        # Here, dpi controls the resolution of figure preview in interactive environment
        fig, axs = plt.subplots(2, 2, figsize=figure_size, dpi=300)
        fig.tight_layout(h_pad=0.1, w_pad=0.1)
        for ax in axs.ravel():
            ax.axis("off")
        for row, ax in zip(people_data.iloc[0:end_ind].iterrows(), axs.ravel()):
            _make_card(
                row[1],
                ax,
                first_name_col,
                last_name_col,
                photo_path_col,
                path_to_default_photo,
                name_x_coord,
                name_y_coord,
                name_font_size,
                desc_padding,
                desc_font_size,
                photo_axes_bounds,
                stats=stats,
            )
        plt.show()  # Needs to be called explicitly to properly render mathtext in bold


def _make_card(
    row: pd.Series,
    ax: axes.Axes,
    first_name_col: str,
    last_name_col: str,
    photo_path_col: str,
    path_to_default_photo: str,
    name_x_coord: float,
    name_y_coord: float,
    name_font_size: float,
    desc_padding: float,
    desc_font_size: float,
    photo_axes_bounds: tuple[float, float, float, float],
    stats: StatsDict,
) -> None:
    """Create a single intro card by plotting an individual's name, photo, and
    description on a Matplotlib Axes. Private function.

    :param row: The row in ``people_data`` from which to create the intro card. Each row
        represents an individual.
    :type row: pd.Series
    :param ax: The Matplotlib Axes object on which to plot the individual's name, photo,
        and description string
    :type ax: mpl.axes.Axes
    :param first_name_col: The name of the column (Series) in ``people_data`` that
        houses first names
    :type first_name_col: str
    :param last_name_col: The name of the column (Series) in ``people_data`` that houses
        last names
    :type last_name_col: str
    :param photo_path_col: The name of the column (Series) in ``people_data`` that
        houses paths to individuals' photos. The photos must be of a type that Pillow
        supports (e.g., PNG, JPG). Paths can be relative or absolute.
    :type photo_path_col: str
    :param path_to_default_photo: The path to the photo to use if an individual does not
        have a photo path listed ``people_data``. This default photo will also be used
        if there is indeed a photo path specified but the photo cannot be found at that
        location. The photo must be of a type that Pillow supports (e.g., PNG, JPG). If
        specifying this argument using a single-backlash separator, make sure to use a
        raw string.
    :type path_to_default_photo: str
    :param figure_size: The size of the figure that Matplotlib will create when plotting
        a batch of four intro cards on it. The first entry in this tuple is the width of
        the figure and the second is the height (both in inches). Each figure will
        ultimately become its own page in the PDF.
    :type figure_size: tuple[float, float]
    :param name_x_coord: The (Axes-relative) x-coordinate of the individual's name on
        their intro card (which is a Matplotlib Axes). This will also be the
        x-coordinate of the individual's description.
    :type name_x_coord: float
    :param name_y_coord: The (Axes-relative) y-coordinate of the individual's name on
        their intro card (which is a Matplotlib Axes)
    :type name_y_coord: float
    :param name_font_size: The font size of the individual's name on their intro card
    :type name_font_size: float
    :param desc_padding: The amount of padding (in Axes-relative coordinates) below the
        lower bound of the name's bounding box, after which to begin plotting the
        individual's description
    :type desc_padding: float
    :param desc_font_size: The font size of the individual's description on their intro
        card. If this font size would cause the lower bound of the description's
        bounding box to come within 0.02 of the bottom of any individual's intro card
        (or even exceed it and be cut off), then this font size will be iteratively
        reduced by 5% on that specific intro card until this is no longer the case.
    :type desc_font_size: float
    :param photo_axes_bounds: The bounds of the photo Axes on individuals' intro cards
        (the photo Axes is inset within the main intro card Axes). The bounds should be
        given as (x0, y0, width, height), where x0 and y0 represent the lower-left
        corner of the photo Axes. The photo will ultimately grow from the upper-left
        corner of this bounding box with a fixed aspect ratio. All coordinates are Axes-
        relative.
    :type photo_axes_bounds: tuple[float, float, float, float]
    :param stats: Metadata pertaining to the number of intro cards that were created,
        the number of people for whom cards needed to be generated, and the names of
        people whose photos could not be found or read
    :type stats: StatsDict
    :return: None
    :rtype: NoneType
    """
    ax.axis("on")
    ax.patch.set_edgecolor("black")
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)

    name_right_padding = 0.02  # Padding on right edge of figure for _WrapText
    # Plot name
    name_text = _WrapText(
        name_x_coord,
        name_y_coord,
        f"{row['Full Name']}",
        fontsize=name_font_size,
        width=1 - name_x_coord - name_right_padding,
        widthcoords=ax.transAxes,
        transform=ax.transAxes,
        fontweight="bold",
        va="top",
        ha="left",
    )
    ax.add_artist(name_text)

    name_text_bbox = name_text.get_window_extent()  # In display coordinates
    name_text_bbox_ax_coords = name_text_bbox.transformed(ax.transAxes.inverted())
    desc_y1_coord = name_text_bbox_ax_coords.y0 - desc_padding

    # Plot the description
    # If the provided font size would cause its bottom boundary to come within 0.02
    # of the bottom of the card or exceed the bottom of the card (and therefore be
    # cut off), iteratively reduce the font size by 5% until this is no longer the case.
    while True:
        desc_text = _WrapText(
            name_x_coord,
            desc_y1_coord,
            _get_description_string_from_row(
                row, first_name_col, last_name_col, photo_path_col
            ),
            fontsize=desc_font_size,
            width=1 - name_x_coord - name_right_padding,
            widthcoords=ax.transAxes,
            transform=ax.transAxes,
            va="top",
            linespacing=1.67,
        )
        ax.add_artist(desc_text)
        desc_text_bbox = desc_text.get_window_extent()  # In display coordinates
        desc_text_bbox_ax_coords = desc_text_bbox.transformed(ax.transAxes.inverted())
        if desc_text_bbox_ax_coords.y0 >= 0.02:
            break
        else:
            desc_text.remove()
            desc_font_size = desc_font_size * 0.95

    if not row[photo_path_col] == "":
        if not os.path.exists(row[photo_path_col]):
            person_status = "WARNING"
            person_status_msg = "Photo path provided but photo not found; default used"
            stats["people_with_photo_warnings"].append(row["Full Name"])
            img_to_open = path_to_default_photo
        else:
            try:
                img = Image.open(row[photo_path_col])
                img.close()
                person_status = "SUCCESS"
                person_status_msg = "Photo path provided and photo read"
                img_to_open = row[photo_path_col]
            except OSError:
                person_status = "WARNING"
                person_status_msg = (
                    f"Could not read photo at `{row[photo_path_col]}`; default used"
                )
                stats["people_with_photo_warnings"].append(row["Full Name"])
                img_to_open = path_to_default_photo
    else:
        person_status = "SUCCESS"
        person_status_msg = "No photo path provided"
        img_to_open = path_to_default_photo

    ax_inset = ax.inset_axes(photo_axes_bounds, anchor="NW")
    ax_inset.imshow(Image.open(img_to_open))
    ax_inset.tick_params(axis="both", which="both", length=0)
    ax_inset.set_xticklabels([])
    ax_inset.set_yticklabels([])
    ax_inset.spines[["top", "bottom", "left", "right"]].set_visible(True)
    ax_inset.spines[["top", "bottom", "left", "right"]].set_color("black")
    ax_inset.spines[["top", "bottom", "left", "right"]].set_linewidth(0.1)

    current_progress_for_logging_message = (
        f"[{stats['number_of_cards_created'] + 1}/{stats['number_of_cards_to_create']}]"
    )
    person_logging_message = (
        f"{current_progress_for_logging_message} {person_status} "
        f": {row['Full Name']} - {person_status_msg}"
    )
    logger.info(person_logging_message)
    stats["number_of_cards_created"] += 1


def _get_description_string_from_row(
    row: pd.Series, first_name_col: str, last_name_col: str, photo_path_col: str
) -> str:
    """Return a string that, for a given row/individual, lists all their "column name:
    attribute value" pairings for each column in ``people_data`` (except columns related
    to names or photo path). Private function.

    Each "column name: attribute value" pairing is separated by a new line, and each
    "column name" is bolded (by wrapping it in appropriate Mathtex characters). Text on
    any given line is wrapped, such that it approaches -- but does not touch -- the
    right border of the card. If an individual's "attribute value" is left blank, then
    that particular "column name: attribute value" pairing will be omitted from the
    description string.

    :param row: The row in ``people_data`` to describe. Each row represents an
        individual.
    :type row: pd.Series
    :param first_name_col: The name of the column (Series) in ``people_data`` that
        houses first names
    :type first_name_col: str
    :param last_name_col: The name of the column (Series) in ``people_data`` that houses
        last names
    :type last_name_col: str
    :param photo_path_col: The name of the column (Series) in ``people_data`` that
        houses photo paths. Paths can be relative or absolute.
    :type photo_path_col: str
    :return: A formatted description string listing all the appropriate "column name:
        attribute value" pairings of `row`
    :rtype: str
    """
    name_and_photo_cols = ["Full Name", first_name_col, last_name_col, photo_path_col]
    row_attributes_ex_names_and_photo = row.drop(name_and_photo_cols)

    desc_string_components = [
        f"${column_name}:$ {attribute_value}"
        for column_name, attribute_value in row_attributes_ex_names_and_photo.items()
        if not attribute_value == ""
    ]

    return "\n".join(desc_string_components)


class _WrapText(Text):
    r"""Extend the functionality of :class:`matplotlib.text.Text` by allowing for text to
    be wrapped when a line reaches a certain width (in effect forming a text box).
    Private class.

    With this class, the user can specify the maximum width -- in units of
    ``widthcoords`` -- of a Matplotlib :class:`Text` instance. If the addition of any
    character or word to a line would bring the length of that line beyond the maximum
    width, a new line will be inserted and that character or word will start the new
    line. The class does this by inhering from :class:`matplotlib.text.Text` and
    overriding its :meth:`_get_wrap_line_width` method, ultimately creating a new
    :class:`matplotlib.text.Text` artist. Besides ``width`` and ``widthcoords``, all
    arguments passed when instantiating this class (including ``kwargs``) are passed to
    :class:`matplotlib.text.Text`.

    (This implementation comes from a Github Gist posted by user "dneuman".
    `Link to Gist <https://gist.github.com/dneuman/90af7551c258733954e3b1d1c17698fe>`_.)

    :param x: The x-coordinate of the text. All subsequent code in this module converts
        this number to an Axes-relative coordinate (instead of the default transData) by
        passing ``transform=ax.transAxes`` to the constructor., defaults to 0
    :type x: float, optional
    :param y: The y-coordinate of the text. All subsequent code in this module converts
        this number to an Axes-relative coordinate (instead of the default transData) by
        passing ``transform=ax.transAxes`` to the constructor., defaults to 0
    :type y: float, optional
    :param text: The text string to display, defaults to ""
    :type text: str, optional
    :param width: The maximum allowable width of the text to be displayed. Beyond this
        maximum width, the text is wrapped and a new line is started., defaults to 0
    :type width: float, optional
    :param widthcoords: The coordinate system of ``width``, defaults to None (which is
        interpreted downstream in units of screen pixels)
    :type widthcoords: :class:`mpl.transforms.Transform` or None, optional
    """

    def __init__(
        self,
        x: float = 0,
        y: float = 0,
        text: str = "",
        width: float = 0,
        widthcoords: Transform | None = None,
        **kwargs,
    ) -> None:
        r"""Initialize an instance of :class:`_WrapText` at coordinates ``x``, ``y`` with
        string ``text``, with a maximum width of ``width`` expressed in units of
        ``widthcoords``.

        Besides ``width`` and ``widthcoords``, all arguments (including ``kwargs``) of
        this class are passed to :class:`matplotlib.text.Text`.

        :param x: The x-coordinate of the text. All subsequent code in this module
            converts this number to an Axes-relative coordinate (instead of the default
            transData) by passing ``transform=ax.transAxes`` to the constructor.,
            defaults to 0
        :type x: float, optional
        :param y: The y-coordinate of the text. All subsequent code in this module
            converts this number to an Axes-relative coordinate (instead of the default
            transData) by passing ``transform=ax.transAxes`` to the constructor.,
            defaults to 0
        :type y: float, optional
        :param text: The text string to display, defaults to ""
        :type text: str, optional
        :param width: The maximum allowable width of the text to be displayed. Beyond
            this maximum width, the text is wrapped and a new line is started., defaults
            to 0
        :type width: float, optional
        :param widthcoords: The coordinate system of ``width``, defaults to None (which
            is interpreted downstream in units of screen pixels)
        :type widthcoords: :class:`matplotlib.transforms.Transform` or None, optional
        :return: None
        :rtype: NoneType
        """
        Text.__init__(self, x=x, y=y, text=text, wrap=True, clip_on=True, **kwargs)
        if not widthcoords:
            self.width = width
        else:
            a = widthcoords.transform_point([(0, 0), (width, 0)])
            self.width = a[1][0] - a[0][0]

    def _get_wrap_line_width(self) -> float:
        """Return the maximum allowable width of the :class:`_WrapText` instance.
        Private method.

        This method overrides the one implemented by :class:`matplotlib.text.Text`,
        which is what allows the text to be wrapped.

        :return: The maximum allowable width of the :class:`_WrapText` instance, beyond
            which the text is wrapped.
        :rtype: float
        """
        return self.width


def _ceil_div(dividend: float, divisor: float) -> float:
    """Perform ceiling division using upside-down floor division, which avoids
    introducing floating-point error. Private function.

    :param dividend: The dividend of the ceiling division operation
    :type dividend: float
    :param divisor: The divisor of the ceiling division operation
    :type divisor: float
    :return: The result of the ceiling division
    :rtype: float
    """
    return -(dividend // -divisor)


def _format_data_and_derive_full_names(
    df: pd.DataFrame, first_name_col: str, last_name_col: str, photo_path_col: str
) -> pd.DataFrame:
    """Format DataFrame for Mathtex compatibility and create Full Name column. Private
    function.

    This function replaces null values with empty strings, converts all values to
    strings, and trims whitespace. It also creates a "Full Name" column by combining the
    first and last name columns. Non-name and non-photo columns are formatted for
    MathTeX compatibility by removing forbidden characters (~, ^, \\) from column names,
    escaping special MathTeX characters (space, #, $, %, _, {, }) in column names, and
    escaping dollar signs ($) in column values. Name-related and photo path columns
    retain their original column names.

    :param df: DataFrame to process, containing individual records with their attributes
    :type df: pd.DataFrame
    :param first_name_col: Name of the column containing first names
    :type first_name_col: str
    :param last_name_col: Name of the column containing last names
    :type last_name_col: str
    :param photo_path_col: Name of the column containing photo file paths
    :type photo_path_col: str
    :return: Processed DataFrame with Mathtex-compatible formatting and Full Name column
    :rtype: pd.DataFrame
    """
    df = df.fillna("").astype(str).apply(lambda x: x.str.strip())

    df["Full Name"] = df[first_name_col].str.cat(df[last_name_col], sep=" ").str.strip()

    name_and_photo_cols = ["Full Name", first_name_col, last_name_col, photo_path_col]

    # Format non-name/photo columns for Mathtex
    forbidden_chars_in_col_names = ["~", "^", "\\"]
    prepend_with_backslash_in_col_names = [" ", "#", "$", "%", "_", "{", "}"]

    new_columns = {}
    for col in df.columns:
        if col not in name_and_photo_cols:
            # Prepend backslash to any dollar signs in the values
            df[col] = df[col].str.replace("$", r"\$")
            # Derive formatted column names
            formatted_col = col.strip()
            for char in forbidden_chars_in_col_names:
                formatted_col = formatted_col.replace(char, "")
            for char in prepend_with_backslash_in_col_names:
                formatted_col = formatted_col.replace(char, rf"\{char}")
            new_columns[col] = formatted_col
        else:
            new_columns[col] = col

    df = df.rename(columns=new_columns)
    return df
