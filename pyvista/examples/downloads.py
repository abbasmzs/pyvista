"""Downloadable datasets collected from various sources.

Once downloaded, these datasets are stored locally allowing for the
rapid reuse of these datasets.

Examples
--------
>>> from pyvista import examples
>>> mesh = examples.download_saddle_surface()
>>> mesh.plot()

"""

from functools import partial
import glob
import os
import shutil
from typing import Union
from urllib.request import urlretrieve
import zipfile

import numpy as np

import pyvista
from pyvista import _vtk
from pyvista.core.errors import VTKVersionError

CACHE_VERSION = 2


def _check_examples_path():
    """Check if the examples path exists."""
    if not pyvista.EXAMPLES_PATH:
        raise FileNotFoundError(
            'EXAMPLES_PATH does not exist.  Try setting the '
            'environment variable `PYVISTA_USERDATA_PATH` '
            'to a writable path and restarting python'
        )


def _cache_version(cache_version_file) -> int:
    """Return the cache version."""
    if os.path.isfile(cache_version_file):
        with open(cache_version_file) as fid:
            try:
                return int(fid.read())
            except:
                pass
    return 0


def _verify_cache_integrity():  # pragma: no cover
    """Verify that the version of the cache matches the expected version.

    Clears cache when there is a version mismatch. This avoids any potential
    issues with old file structures due to changed download methods.

    """
    cache_version_file = os.path.join(pyvista.EXAMPLES_PATH, 'VERSION')
    cache_version = _cache_version(cache_version_file)

    # clear with no version file or an old cache version
    if cache_version < CACHE_VERSION:
        delete_downloads()
        with open(cache_version_file, 'w') as fid:
            fid.write(str(CACHE_VERSION))


def delete_downloads():
    """Delete all downloaded examples to free space or update the files.

    Returns
    -------
    bool
        Returns ``True``.

    Examples
    --------
    Delete all local downloads.

    >>> from pyvista import examples
    >>> examples.delete_downloads()  # doctest:+SKIP
    True

    """
    _check_examples_path()
    if os.path.isdir(pyvista.EXAMPLES_PATH):
        shutil.rmtree(pyvista.EXAMPLES_PATH)
    os.makedirs(pyvista.EXAMPLES_PATH)
    return True


def _decompress(filename, output_path):
    _check_examples_path()
    zip_ref = zipfile.ZipFile(filename, 'r')
    zip_ref.extractall(output_path)
    return zip_ref.close()


def _get_vtk_file_url(filename):
    return f'https://github.com/pyvista/vtk-data/raw/master/Data/{filename}'


def _http_request(url, progress_bar=False):  # pragma: no cover
    """Download a file from a url using ``urlretrieve``.

    Inspired by https://stackoverflow.com/a/53877507/3369879

    Parameters
    ----------
    url : str
        URL of the file to download.

    progress_bar : bool, default: False
        Display a progress_bar bar when downloading the file.

    Returns
    -------
    str
        Filename of the downloaded file.

    http.client.HTTPMessage
        The headers returned by urlretrieve.

    """
    if progress_bar:

        try:
            from tqdm import tqdm
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                'Install `tqdm` for download progress bars with:\n\n' 'pip install tqdm'
            ) from None

        class DownloadProgressBar(tqdm):
            """Download progress bar."""

            def update_to(self, b=1, bsize=1, tsize=None):
                """Update the progress bar."""
                if tsize is not None:
                    self.total = tsize
                    self.update(b * bsize - self.n)

        desc = f"Downloading {url.split('/')[-1]}"

        with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, desc=desc) as pbar:
            return urlretrieve(url, reporthook=pbar.update_to)
    else:
        return urlretrieve(url)


def _repo_file_request(repo_path, filename):
    return os.path.join(repo_path, 'Data', filename), None


def _retrieve_file(retriever, filename):
    """Retrieve a file and cache it in pyvsita.EXAMPLES_PATH.

    Parameters
    ----------
    retriever : str or callable
        If str, it is treated as a url.
        If callable, the function must take no arguments and must
        return a tuple like (file_path, resp), where file_path is
        the path to the file to use.
    filename : str
        The name of the file.

    Returns
    -------
    str
        Path to the downloaded file.
    http.client.HTTPMessage
        HTTP download Response.

    """
    _check_examples_path()

    # First check if file has already been downloaded
    local_path = os.path.join(pyvista.EXAMPLES_PATH, filename)
    if os.path.isfile(local_path):
        return local_path, None

    if isinstance(retriever, str):  # pragma: no cover
        retriever = partial(_http_request, retriever, progress_bar=True)
    saved_file, resp = retriever()

    # Make sure folder exists
    local_dir = os.path.dirname(local_path)
    if not os.path.isdir(local_dir):
        os.makedirs(local_dir)

    if pyvista.VTK_DATA_PATH is None:
        shutil.move(saved_file, local_path)
    else:
        if os.path.isdir(saved_file):
            shutil.copytree(saved_file, local_path)
        else:
            shutil.copy(saved_file, local_path)

    return local_path, resp


def _retrieve_zip(retriever, filename):
    """Retrieve a zip and cache it in pyvista.EXAMPLES_PATH.

    Parameters
    ----------
    retriever : str or callable
        If str, it is treated as a URL.
        If callable, the function must take no arguments and must
        return a tuple like (file_path, resp), where file_path is
        the path to the file to use.

    filename : str
        The name of the file.

    Returns
    -------
    str
        Path of the directory with the unzipped files.

    http.client.HTTPMessage
        HTTP download Response.

    """
    _check_examples_path()

    # First check if file has already been downloaded
    local_path_zip_dir = os.path.join(pyvista.EXAMPLES_PATH, filename)
    if os.path.isdir(local_path_zip_dir):
        return local_path_zip_dir, None
    if isinstance(retriever, str):  # pragma: no cover
        retriever = partial(_http_request, retriever)
    saved_file, resp = retriever()

    # Edge case where retriever saves to an identical location as the saved
    # file name.
    if filename == saved_file:  # pragma: no cover
        new_saved_file = saved_file + '.download'
        os.rename(saved_file, new_saved_file)
        saved_file = new_saved_file

    # Make sure directory exists
    if not os.path.isdir(local_path_zip_dir):
        os.makedirs(local_path_zip_dir)

    # move the tmp file to the new directory
    local_path_zip_file = os.path.join(local_path_zip_dir, os.path.basename(filename))
    if pyvista.VTK_DATA_PATH is None:
        shutil.move(saved_file, local_path_zip_file)
    else:  # pragma: no cover
        shutil.copy(saved_file, local_path_zip_file)

    # decompress and remove the zip file to save space
    _decompress(local_path_zip_file, local_path_zip_dir)
    os.remove(local_path_zip_file)
    return local_path_zip_dir, resp


def _download_file(filename, progress_bar=False):
    """Download a file from https://github.com/pyvista/vtk-data/master/Data.

    If ``pyvista.VTK_DATA_PATH`` is set, then the remote repository is expected
    to be a local git repository.

    Parameters
    ----------
    filename : str
        Path within https://github.com/pyvista/vtk-data/master/Data to download
        the file from.

    progress_bar : bool, default: False
        Display a progress_bar bar when downloading the file. This is ignored
        when ``VTK_DATA_PATH`` is set.

    Examples
    --------
    Download the ``'blood_vessels.zip'`` file from
    https://github.com/pyvista/vtk-data/tree/master/Data/pvtu_blood_vessels.
    This returns a path of the unzipped archive.

    >>> path, _ = _download_file('pvtu_blood_vessels/blood_vessels.zip')  # doctest:+SKIP
    >>> path  # doctest:+SKIP
    /home/user/.local/share/pyvista/examples/blood_vessels

    Download the ``'emote.jpg'`` file.

    >>> path, _ = _download_file('emote.jpg')  # doctest:+SKIP
    >>> path  # doctest:+SKIP
    /home/user/.local/share/pyvista/examples/emote.jpg

    """
    if pyvista.VTK_DATA_PATH is None:
        url = _get_vtk_file_url(filename)
        retriever = partial(_http_request, url, progress_bar=progress_bar)
    else:
        if not os.path.isdir(pyvista.VTK_DATA_PATH):
            raise FileNotFoundError(
                f'VTK data repository path does not exist at:\n\n{pyvista.VTK_DATA_PATH}'
            )
        if not os.path.isdir(os.path.join(pyvista.VTK_DATA_PATH, 'Data')):
            raise FileNotFoundError(
                f'VTK data repository does not have "Data" folder at:\n\n{pyvista.VTK_DATA_PATH}'
            )
        retriever = partial(_repo_file_request, pyvista.VTK_DATA_PATH, filename)

    if pyvista.get_ext(filename) == '.zip':
        return _retrieve_zip(retriever, filename)
    return _retrieve_file(retriever, filename)


def _download_and_read(filename, texture=False, file_format=None, load=True, progress_bar=False):
    """Download and read a file.

    Parameters
    ----------
    filename : str
        Path to the filename. This cannot be a zip file.

    texture : bool, optional
        ``True`` when file being read is a texture.

    file_format : str, optional
        Override the file format with a different extension.

    load : bool, optional
        Read the file. Default ``True``, when ``False``, return the path to the
        file.

    progress_bar : bool, default: False
        Display a progress_bar bar when downloading the file. This is ignored
        when ``VTK_DATA_PATH`` is set.

    Returns
    -------
    pyvista.DataSet or str
        Dataset or path to the file depending on the ``load`` parameter.

    """
    saved_file, _ = _download_file(filename, progress_bar=progress_bar)
    if pyvista.get_ext(filename) == '.zip':  # pragma: no cover
        raise ValueError('Cannot download and read an archive file')

    if not load:
        return saved_file
    if texture:
        return pyvista.read_texture(saved_file)
    return pyvista.read(saved_file, file_format=file_format)


###############################################################################


def download_masonry_texture(load=True):  # pragma: no cover
    """Download masonry texture.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.DataSet or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Create plot the masonry testure on a surface.

    >>> import pyvista
    >>> from pyvista import examples
    >>> texture = examples.download_masonry_texture()
    >>> surf = pyvista.Cylinder()
    >>> surf.plot(texture=texture)

    See :ref:`ref_texture_example` for an example using this
    dataset.

    """
    return _download_and_read('masonry.bmp', texture=True, load=load)


def download_usa_texture(load=True):  # pragma: no cover
    """Download USA texture.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.DataSet or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> import pyvista
    >>> from pyvista import examples
    >>> dataset = examples.download_usa_texture()
    >>> dataset.plot(cpos="xy")

    """
    return _download_and_read('usa_image.jpg', texture=True, load=load)


def download_puppy_texture(load=True):  # pragma: no cover
    """Download puppy texture.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.DataSet or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_puppy_texture()
    >>> dataset.plot(cpos="xy")

    See :ref:`ref_texture_example` for an example using this
    dataset.

    """
    return _download_and_read('puppy.jpg', texture=True, load=load)


def download_puppy(load=True):  # pragma: no cover
    """Download puppy dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_puppy()
    >>> dataset.plot(cpos='xy', rgba=True)

    """
    return _download_and_read('puppy.jpg', load=load)


def download_usa(load=True):  # pragma: no cover
    """Download usa dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.DataSet or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_usa()
    >>> dataset.plot(style="wireframe", cpos="xy")

    """
    return _download_and_read('usa.vtk', load=load)


def download_st_helens(load=True):  # pragma: no cover
    """Download Saint Helens dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_st_helens()
    >>> dataset.plot(cmap="gist_earth")

    This dataset is used in the following examples:

    * :ref:`colormap_example`
    * :ref:`ref_lighting_properties_example`
    * :ref:`plot_opacity_example`
    * :ref:`orbiting_example`
    * :ref:`plot_over_line_example`
    * :ref:`plotter_lighting_example`
    * :ref:`themes_example`

    """
    return _download_and_read('SainteHelens.dem', load=load)


def download_bunny(load=True):  # pragma: no cover
    """Download bunny dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    See Also
    --------
    download_bunny_coarse

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_bunny()
    >>> dataset.plot(cpos="xy")

    This dataset is used in the following examples:

    * :ref:`read_file_example`
    * :ref:`clip_with_surface_example`
    * :ref:`extract_edges_example`
    * :ref:`subdivide_example`
    * :ref:`silhouette_example`
    * :ref:`light_types_example`

    """
    return _download_and_read('bunny.ply', load=load)


def download_bunny_coarse(load=True):  # pragma: no cover
    """Download coarse bunny dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    See Also
    --------
    download_bunny

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_bunny_coarse()
    >>> dataset.plot(cpos="xy")

    * :ref:`read_file_example`
    * :ref:`clip_with_surface_example`
    * :ref:`subdivide_example`

    """
    result = _download_and_read('Bunny.vtp', load=load)
    if load:
        result.verts = np.array([], dtype=np.int32)
    return result


def download_cow(load=True):  # pragma: no cover
    """Download cow dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_cow()
    >>> dataset.plot(cpos="xy")

    This dataset is used in the following examples:

    * :ref:`extract_edges_example`
    * :ref:`mesh_quality_example`
    * :ref:`rotate_example`
    * :ref:`linked_views_example`
    * :ref:`light_actors_example`

    """
    return _download_and_read('cow.vtp', load=load)


def download_cow_head(load=True):  # pragma: no cover
    """Download cow head dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_cow_head()
    >>> dataset.plot(cpos="xy")

    """
    return _download_and_read('cowHead.vtp', load=load)


def download_faults(load=True):  # pragma: no cover
    """Download faults dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_faults()
    >>> dataset.plot(line_width=4)

    """
    return _download_and_read('faults.vtk', load=load)


def download_tensors(load=True):  # pragma: no cover
    """Download tensors dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_tensors()
    >>> dataset.plot()

    """
    return _download_and_read('tensors.vtk', load=load)


def download_head(load=True):  # pragma: no cover
    """Download head dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> import pyvista
    >>> from pyvista import examples
    >>> dataset = examples.download_head()
    >>> pl = pyvista.Plotter()
    >>> _ = pl.add_volume(dataset, cmap="cool", opacity="sigmoid_6")
    >>> pl.camera_position = [
    ...     (-228.0, -418.0, -158.0),
    ...     (94.0, 122.0, 82.0),
    ...     (-0.2, -0.3, 0.9)
    ... ]
    >>> pl.show()

    See :ref:`volume_rendering_example` for an example using this
    dataset.

    """
    _download_file('HeadMRVolume.raw')
    return _download_and_read('HeadMRVolume.mhd', load=load)


def download_bolt_nut(load=True):  # pragma: no cover
    """Download bolt nut dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.MultiBlock or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> import pyvista
    >>> from pyvista import examples
    >>> dataset = examples.download_bolt_nut()
    >>> pl = pyvista.Plotter()
    >>> _ = pl.add_volume(
    ...         dataset, cmap="coolwarm", opacity="sigmoid_5", show_scalar_bar=False,
    ... )
    >>> pl.camera_position = [
    ...     (194.6, -141.8, 182.0),
    ...     (34.5, 61.0, 32.5),
    ...     (-0.229, 0.45, 0.86)
    ... ]
    >>> pl.show()

    See :ref:`volume_rendering_example` for an example using this
    dataset.

    """
    if not load:
        return (_download_and_read('bolt.slc', load=load), _download_and_read('nut.slc', load=load))
    blocks = pyvista.MultiBlock()
    blocks['bolt'] = _download_and_read('bolt.slc')
    blocks['nut'] = _download_and_read('nut.slc')
    return blocks


def download_clown(load=True):  # pragma: no cover
    """Download clown dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_clown()
    >>> dataset.plot()

    """
    return _download_and_read('clown.facet', load=load)


def download_topo_global(load=True):  # pragma: no cover
    """Download topo dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_topo_global()
    >>> dataset.plot(cmap="gist_earth")

    This dataset is used in the following examples:

    * :ref:`surface_normal_example`
    * :ref:`background_image_example`

    """
    return _download_and_read('EarthModels/ETOPO_10min_Ice.vtp', load=load)


def download_topo_land(load=True):  # pragma: no cover
    """Download topo land dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_topo_land()
    >>> dataset.plot(clim=[-2000, 3000], cmap="gist_earth", show_scalar_bar=False)

    This dataset is used in the following examples:

    * :ref:`geodesic_example`
    * :ref:`background_image_example`

    """
    return _download_and_read('EarthModels/ETOPO_10min_Ice_only-land.vtp', load=load)


def download_coastlines(load=True):  # pragma: no cover
    """Download coastlines dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_coastlines()
    >>> dataset.plot()

    """
    return _download_and_read('EarthModels/Coastlines_Los_Alamos.vtp', load=load)


def download_knee(load=True):  # pragma: no cover
    """Download knee dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_knee()
    >>> dataset.plot(cpos="xy", show_scalar_bar=False)

    This dataset is used in the following examples:

    * :ref:`plot_opacity_example`
    * :ref:`volume_rendering_example`
    * :ref:`slider_bar_widget_example`

    """
    return _download_and_read('DICOM_KNEE.dcm', load=load)


def download_knee_full(load=True):  # pragma: no cover
    """Download full knee dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_knee_full()
    >>> cpos = [
    ...     (-381.74, -46.02, 216.54),
    ...     (74.8305, 89.2905, 100.0),
    ...     (0.23, 0.072, 0.97)
    ... ]
    >>> dataset.plot(volume=True, cmap="bone", cpos=cpos, show_scalar_bar=False)

    This dataset is used in the following examples:

    * :ref:`volume_rendering_example`
    * :ref:`slider_bar_widget_example`

    """
    return _download_and_read('vw_knee.slc', load=load)


def download_lidar(load=True):  # pragma: no cover
    """Download lidar dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_lidar()
    >>> dataset.plot(cmap="gist_earth")

    This dataset is used in the following examples:

    * :ref:`create_point_cloud`
    * :ref:`ref_edl`

    """
    return _download_and_read('kafadar-lidar-interp.vtp', load=load)


def download_exodus(load=True):  # pragma: no cover
    """Sample ExodusII data file.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.MultiBlock or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_exodus()
    >>> dataset.plot()

    """
    return _download_and_read('mesh_fs8.exo', load=load)


def download_nefertiti(load=True):  # pragma: no cover
    """Download mesh of Queen Nefertiti.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_nefertiti()
    >>> dataset.plot(cpos="xz")

    This dataset is used in the following examples:

    * :ref:`surface_normal_example`
    * :ref:`extract_edges_example`
    * :ref:`show_edges_example`
    * :ref:`ref_edl`
    * :ref:`pbr_example`
    * :ref:`box_widget_example`

    """
    path, _ = _download_file('nefertiti.ply.zip')
    filename = os.path.join(path, 'nefertiti.ply')
    if not load:
        return filename
    return pyvista.read(filename)


def download_blood_vessels(load=True):  # pragma: no cover
    """Download data representing the bifurcation of blood vessels.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_blood_vessels()
    >>> dataset.plot()

    This dataset is used in the following examples:

    * :ref:`read_parallel_example`
    * :ref:`streamlines_example`
    * :ref:`integrate_example`

    """
    directory, _ = _download_file('pvtu_blood_vessels/blood_vessels.zip')
    filename = os.path.join(directory, 'blood_vessels', 'T0000000500.pvtu')

    if not load:
        return filename
    mesh = pyvista.read(filename)
    mesh.set_active_vectors('velocity')
    return mesh


def download_iron_protein(load=True):  # pragma: no cover
    """Download iron protein dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_iron_protein()
    >>> dataset.plot(volume=True, cmap='blues')

    """
    return _download_and_read('ironProt.vtk', load=load)


def download_tetrahedron(load=True):  # pragma: no cover
    """Download tetrahedron dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Shrink and plot the dataset to show it is composed of several
    tetrahedrons.

    >>> from pyvista import examples
    >>> dataset = examples.download_tetrahedron()
    >>> dataset.shrink(0.85).plot()

    """
    return _download_and_read('Tetrahedron.vtu', load=load)


def download_saddle_surface(load=True):  # pragma: no cover
    """Download saddle surface dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_saddle_surface()
    >>> dataset.plot()

    See :ref:`interpolate_example` for an example using this
    dataset.

    """
    return _download_and_read('InterpolatingOnSTL_final.stl', load=load)


def download_sparse_points(load=True):  # pragma: no cover
    """Download sparse points data.

    Used with :func:`download_saddle_surface`.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_sparse_points()
    >>> dataset.plot(scalars="val", render_points_as_spheres=True, point_size=50)

    See :ref:`interpolate_example` for an example using this
    dataset.

    """
    saved_file, _ = _download_file('sparsePoints.txt')
    if not load:
        return saved_file
    points_reader = _vtk.vtkDelimitedTextReader()
    points_reader.SetFileName(saved_file)
    points_reader.DetectNumericColumnsOn()
    points_reader.SetFieldDelimiterCharacters('\t')
    points_reader.SetHaveHeaders(True)
    table_points = _vtk.vtkTableToPolyData()
    table_points.SetInputConnection(points_reader.GetOutputPort())
    table_points.SetXColumn('x')
    table_points.SetYColumn('y')
    table_points.SetZColumn('z')
    table_points.Update()
    return pyvista.wrap(table_points.GetOutput())


def download_foot_bones(load=True):  # pragma: no cover
    """Download foot bones dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_foot_bones()
    >>> dataset.plot()

    See :ref:`voxelize_surface_mesh_example` for an example using this
    dataset.

    """
    return _download_and_read('fsu/footbones.ply', load=load)


def download_guitar(load=True):  # pragma: no cover
    """Download guitar dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_guitar()
    >>> dataset.plot()

    """
    return _download_and_read('fsu/stratocaster.ply', load=load)


def download_quadratic_pyramid(load=True):  # pragma: no cover
    """Download quadratic pyramid dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Shrink and plot the dataset to show it is composed of several
    pyramids.

    >>> from pyvista import examples
    >>> dataset = examples.download_quadratic_pyramid()
    >>> dataset.shrink(0.4).plot()

    """
    return _download_and_read('QuadraticPyramid.vtu', load=load)


def download_bird(load=True):  # pragma: no cover
    """Download bird dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_bird()
    >>> dataset.plot(rgba=True, cpos="xy")

    """
    return _download_and_read('Pileated.jpg', load=load)


def download_bird_texture(load=True):  # pragma: no cover
    """Download bird texture.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.Texture or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_bird_texture()
    >>> dataset.plot(cpos="xy")

    """
    return _download_and_read('Pileated.jpg', texture=True, load=load)


def download_office(load=True):  # pragma: no cover
    """Download office dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.StructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_office()
    >>> dataset.contour().plot()

    See :ref:`clip_with_plane_box_example` for an example using this
    dataset.

    """
    return _download_and_read('office.binary.vtk', load=load)


def download_horse_points(load=True):  # pragma: no cover
    """Download horse points dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_horse_points()
    >>> dataset.plot(point_size=1)

    """
    return _download_and_read('horsePoints.vtp', load=load)


def download_horse(load=True):  # pragma: no cover
    """Download horse dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.DataSet or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_horse()
    >>> dataset.plot(smooth_shading=True)

    See :ref:`disabling_mesh_lighting_example` for an example using
    this dataset.

    """
    return _download_and_read('horse.vtp', load=load)


def download_cake_easy(load=True):  # pragma: no cover
    """Download cake dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_cake_easy()
    >>> dataset.plot(rgba=True, cpos="xy")

    """
    return _download_and_read('cake_easy.jpg', load=load)


def download_cake_easy_texture(load=True):  # pragma: no cover
    """Download cake texture.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.Texture or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_cake_easy_texture()
    >>> dataset.plot(cpos="xy")

    """
    return _download_and_read('cake_easy.jpg', texture=True, load=load)


def download_rectilinear_grid(load=True):  # pragma: no cover
    """Download rectilinear grid dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.RectilinearGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Compute the threshold of this dataset.

    >>> from pyvista import examples
    >>> dataset = examples.download_rectilinear_grid()
    >>> dataset.threshold(0.0001).plot()

    """
    return _download_and_read('RectilinearGrid.vtr', load=load)


def download_gourds(zoom=False, load=True):  # pragma: no cover
    """Download gourds dataset.

    Parameters
    ----------
    zoom : bool, optional
        When ``True``, return the zoomed picture of the gourds.

    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_gourds()
    >>> dataset.plot(rgba=True, cpos="xy")

    See :ref:`gaussian_smoothing_example` for an example using
    this dataset.

    """
    if zoom:
        return _download_and_read('Gourds.png', load=load)
    return _download_and_read('Gourds2.jpg', load=load)


def download_gourds_texture(zoom=False, load=True):  # pragma: no cover
    """Download gourds texture.

    Parameters
    ----------
    zoom : bool, optional
        When ``True``, return the zoomed picture of the gourds.

    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.DataSet or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_gourds_texture()
    >>> dataset.plot(cpos="xy")

    """
    if zoom:
        return _download_and_read('Gourds.png', texture=True, load=load)
    return _download_and_read('Gourds2.jpg', texture=True, load=load)


def download_gourds_pnm(load=True):  # pragma: no cover
    """Download gourds dataset from pnm file.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_gourds_pnm()
    >>> dataset.plot(rgba=True, cpos="xy")

    """
    return _download_and_read('Gourds.pnm', load=load)


def download_unstructured_grid(load=True):  # pragma: no cover
    """Download unstructured grid dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_unstructured_grid()
    >>> dataset.plot(show_edges=True)

    """
    return _download_and_read('uGridEx.vtk', load=load)


def download_letter_k(load=True):  # pragma: no cover
    """Download letter k dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_letter_k()
    >>> dataset.plot(cpos="xy")

    """
    return _download_and_read('k.vtk', load=load)


def download_letter_a(load=True):  # pragma: no cover
    """Download letter a dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_letter_a()
    >>> dataset.plot(cpos="xy", show_edges=True)

    See :ref:`cell_centers_example` for an example using
    this dataset.

    """
    return _download_and_read('a_grid.vtk', load=load)


def download_poly_line(load=True):  # pragma: no cover
    """Download polyline dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_poly_line()
    >>> dataset.plot(line_width=5)

    """
    return _download_and_read('polyline.vtk', load=load)


def download_cad_model(load=True):  # pragma: no cover
    """Download cad dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_cad_model()
    >>> dataset.plot()

    See :ref:`read_file_example` for an example using
    this dataset.

    """
    return _download_and_read('42400-IDGH.stl', load=load)


def download_frog(load=True):  # pragma: no cover
    """Download frog dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> cpos = [
    ...     [ 8.4287e+02, -5.7418e+02, -4.4085e+02],
    ...     [ 2.4950e+02,  2.3450e+02,  1.0125e+02],
    ...     [-3.2000e-01,  3.5000e-01, -8.8000e-01]
    ... ]
    >>> dataset = examples.download_frog()
    >>> dataset.plot(volume=True, cpos=cpos)

    See :ref:`volume_rendering_example` for an example using
    this dataset.

    """
    # TODO: there are other files with this
    _download_file('froggy/frog.zraw')
    return _download_and_read('froggy/frog.mhd', load=load)


def download_chest(load=True):  # pragma: no cover
    """Download chest dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_chest()
    >>> dataset.plot(cpos="xy")

    See :ref:`volume_rendering_example` for an example using
    this dataset.

    """
    return _download_and_read('MetaIO/ChestCT-SHORT.mha', load=load)


def download_prostate(load=True):  # pragma: no cover
    """Download prostate dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_prostate()
    >>> dataset.plot(cpos="xy")

    """
    return _download_and_read('prostate.img', load=load)


def download_filled_contours(load=True):  # pragma: no cover
    """Download filled contours dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_filled_contours()
    >>> dataset.plot(cpos="xy")

    """
    return _download_and_read('filledContours.vtp', load=load)


def download_doorman(load=True):  # pragma: no cover
    """Download doorman dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_doorman()
    >>> dataset.plot(cpos="xy")

    See :ref:`read_file_example` for an example using
    this dataset.

    """
    # TODO: download textures as well
    return _download_and_read('doorman/doorman.obj', load=load)


def download_mug(load=True):  # pragma: no cover
    """Download mug dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.MultiBlock or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_mug()
    >>> dataset.plot()

    """
    return _download_and_read('mug.e', load=load)


def download_oblique_cone(load=True):  # pragma: no cover
    """Download oblique cone dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_oblique_cone()
    >>> dataset.plot()

    """
    return _download_and_read('ObliqueCone.vtp', load=load)


def download_emoji(load=True):  # pragma: no cover
    """Download emoji dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_emoji()
    >>> dataset.plot(rgba=True, cpos="xy")

    """
    return _download_and_read('emote.jpg', load=load)


def download_emoji_texture(load=True):  # pragma: no cover
    """Download emoji texture.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.Texture or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_emoji_texture()
    >>> dataset.plot(cpos="xy")

    """
    return _download_and_read('emote.jpg', texture=True, load=load)


def download_teapot(load=True):  # pragma: no cover
    """Download teapot dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_teapot()
    >>> dataset.plot(cpos="xy")

    This dataset is used in the following examples:

    * :ref:`read_file_example`
    * :ref:`cell_centers_example`

    """
    return _download_and_read('teapot.g', load=load)


def download_brain(load=True):  # pragma: no cover
    """Download brain dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_brain()
    >>> dataset.plot(volume=True)

    This dataset is used in the following examples:

    * :ref:`gaussian_smoothing_example`
    * :ref:`slice_example`
    * :ref:`depth_peeling_example`
    * :ref:`moving_isovalue_example`
    * :ref:`plane_widget_example`

    """
    return _download_and_read('brain.vtk', load=load)


def download_structured_grid(load=True):  # pragma: no cover
    """Download structured grid dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.StructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_structured_grid()
    >>> dataset.plot(show_edges=True)

    """
    return _download_and_read('StructuredGrid.vts', load=load)


def download_structured_grid_two(load=True):  # pragma: no cover
    """Download structured grid two dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.StructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_structured_grid_two()
    >>> dataset.plot(show_edges=True)

    """
    return _download_and_read('SampleStructGrid.vtk', load=load)


def download_trumpet(load=True):  # pragma: no cover
    """Download trumpet dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_trumpet()
    >>> dataset.plot()

    """
    return _download_and_read('trumpet.obj', load=load)


def download_face(load=True):  # pragma: no cover
    """Download face dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_face()
    >>> dataset.plot()

    See :ref:`decimate_example` for an example using
    this dataset.


    """
    # TODO: there is a texture with this
    return _download_and_read('fran_cut.vtk', load=load)


def download_sky_box_nz(load=True):  # pragma: no cover
    """Download skybox-nz dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_sky_box_nz()
    >>> dataset.plot(rgba=True, cpos="xy")

    """
    return _download_and_read('skybox-nz.jpg', load=load)


def download_sky_box_nz_texture(load=True):  # pragma: no cover
    """Download skybox-nz texture.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.Texture or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_sky_box_nz_texture()
    >>> dataset.plot(cpos="xy")

    """
    return _download_and_read('skybox-nz.jpg', texture=True, load=load)


def download_disc_quads(load=True):  # pragma: no cover
    """Download disc quads dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_disc_quads()
    >>> dataset.plot(show_edges=True)

    """
    return _download_and_read('Disc_BiQuadraticQuads_0_0.vtu', load=load)


def download_honolulu(load=True):  # pragma: no cover
    """Download honolulu dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_honolulu()
    >>> dataset.plot(
    ...     scalars=dataset.points[:, 2],
    ...     show_scalar_bar=False,
    ...     cmap="gist_earth",
    ...     clim=[-50, 800],
    ... )

    """
    return _download_and_read('honolulu.vtk', load=load)


def download_motor(load=True):  # pragma: no cover
    """Download motor dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_motor()
    >>> dataset.plot()

    """
    return _download_and_read('motor.g', load=load)


def download_tri_quadratic_hexahedron(load=True):  # pragma: no cover
    """Download tri quadratic hexahedron dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_tri_quadratic_hexahedron()
    >>> dataset.plot()

    Show non-linear subdivision.

    >>> surf = dataset.extract_surface(nonlinear_subdivision=5)
    >>> surf.plot(smooth_shading=True)

    """
    dataset = _download_and_read('TriQuadraticHexahedron.vtu', load=load)
    if load:
        dataset.clear_data()
    return dataset


def download_human(load=True):  # pragma: no cover
    """Download human dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_human()
    >>> dataset.plot()

    """
    return _download_and_read('Human.vtp', load=load)


def download_vtk(load=True):  # pragma: no cover
    """Download vtk dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_vtk()
    >>> dataset.plot(cpos="xy", line_width=5)

    """
    return _download_and_read('vtk.vtp', load=load)


def download_spider(load=True):  # pragma: no cover
    """Download spider dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_spider()
    >>> dataset.plot()

    """
    return _download_and_read('spider.ply', load=load)


def download_carotid(load=True):  # pragma: no cover
    """Download carotid dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> cpos = [
    ...     [220.96, -24.38, -69.96],
    ...     [135.86, 106.55,  17.72],
    ...     [ -0.25,   0.42,  -0.87]
    ... ]
    >>> dataset = examples.download_carotid()
    >>> dataset.plot(volume=True, cpos=cpos)

    This dataset is used in the following examples:

    * :ref:`glyph_example`
    * :ref:`gradients_example`
    * :ref:`streamlines_example`
    * :ref:`plane_widget_example`

    """
    mesh = _download_and_read('carotid.vtk', load=load)
    if not load:
        return mesh
    mesh.set_active_scalars('scalars')
    mesh.set_active_vectors('vectors')
    return mesh


def download_blow(load=True):  # pragma: no cover
    """Download blow dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> cpos = [
    ...     [71.96, 86.1 , 28.45],
    ...     [ 3.5 , 12.  ,  1.  ],
    ...     [-0.18, -0.19,  0.96]
    ... ]
    >>> dataset = examples.download_blow()
    >>> dataset.plot(
    ...     scalars='displacement1',
    ...     component=1,
    ...     cpos=cpos,
    ...     show_scalar_bar=False,
    ...     smooth_shading=True,
    ... )

    """
    return _download_and_read('blow.vtk', load=load)


def download_shark(load=True):  # pragma: no cover
    """Download shark dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> cpos = [
    ...     [-2.3195e+02, -3.3930e+01,  1.2981e+02],
    ...     [-8.7100e+00,  1.9000e-01, -1.1740e+01],
    ...     [-1.4000e-01,  9.9000e-01,  2.0000e-02]
    ... ]
    >>> dataset = examples.download_shark()
    >>> dataset.plot(cpos=cpos, smooth_shading=True)

    """
    return _download_and_read('shark.ply', load=load)


def download_dragon(load=True):  # pragma: no cover
    """Download dragon dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_dragon()
    >>> dataset.plot(cpos="xy")

    This dataset is used in the following examples:

    * :ref:`floors_example`
    * :ref:`orbiting_example`
    * :ref:`silhouette_example`
    * :ref:`light_shadows_example`

    """
    return _download_and_read('dragon.ply', load=load)


def download_armadillo(load=True):  # pragma: no cover
    """Download armadillo dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Plot the armadillo dataset. Use a custom camera position.

    >>> from pyvista import examples
    >>> cpos = [
    ...     (161.5, 82.1, -330.2),
    ...     (-4.3, 24.5, -1.6),
    ...     (-0.1, 1, 0.12)
    ... ]
    >>> dataset = examples.download_armadillo()
    >>> dataset.plot(cpos=cpos)

    """
    return _download_and_read('Armadillo.ply', load=load)


def download_gears(load=True):  # pragma: no cover
    """Download gears dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Download the dataset, split the bodies, and color each one.

    >>> import numpy as np
    >>> from pyvista import examples
    >>> dataset = examples.download_gears()
    >>> bodies = dataset.split_bodies()
    >>> for i, body in enumerate(bodies):
    ...     bid = np.empty(body.n_points)
    ...     bid[:] = i
    ...     body.point_data["Body ID"] = bid
    >>> bodies.plot(cmap='jet')
    """
    return _download_and_read('gears.stl', load=load)


def download_torso(load=True):  # pragma: no cover
    """Download torso dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_torso()
    >>> dataset.plot(cpos="xz")

    """
    return _download_and_read('Torso.vtp', load=load)


def download_kitchen(split=False, load=True):  # pragma: no cover
    """Download structured grid of kitchen with velocity field.

    Use the ``split`` argument to extract all of the furniture in the
    kitchen.

    Parameters
    ----------
    split : bool, optional
        Optionally split the furniture and return a
        :class:`pyvista.MultiBlock`.

    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.StructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_kitchen()
    >>> dataset.streamlines(n_points=5).plot()

    This dataset is used in the following examples:

    * :ref:`plot_over_line_example`
    * :ref:`line_widget_example`

    """
    mesh = _download_and_read('kitchen.vtk', load=load)
    if not load:
        return mesh
    if not split:
        return mesh
    extents = {
        'door': (27, 27, 14, 18, 0, 11),
        'window1': (0, 0, 9, 18, 6, 12),
        'window2': (5, 12, 23, 23, 6, 12),
        'klower1': (17, 17, 0, 11, 0, 6),
        'klower2': (19, 19, 0, 11, 0, 6),
        'klower3': (17, 19, 0, 0, 0, 6),
        'klower4': (17, 19, 11, 11, 0, 6),
        'klower5': (17, 19, 0, 11, 0, 0),
        'klower6': (17, 19, 0, 7, 6, 6),
        'klower7': (17, 19, 9, 11, 6, 6),
        'hood1': (17, 17, 0, 11, 11, 16),
        'hood2': (19, 19, 0, 11, 11, 16),
        'hood3': (17, 19, 0, 0, 11, 16),
        'hood4': (17, 19, 11, 11, 11, 16),
        'hood5': (17, 19, 0, 11, 16, 16),
        'cookingPlate': (17, 19, 7, 9, 6, 6),
        'furniture': (17, 19, 7, 9, 11, 11),
    }
    kitchen = pyvista.MultiBlock()
    for key, extent in extents.items():
        alg = _vtk.vtkStructuredGridGeometryFilter()
        alg.SetInputDataObject(mesh)
        alg.SetExtent(extent)
        alg.Update()
        result = pyvista.filters._get_output(alg)
        kitchen[key] = result
    return kitchen


def download_tetra_dc_mesh():  # pragma: no cover
    """Download two meshes defining an electrical inverse problem.

    This contains a high resolution forward modeled mesh and a coarse
    inverse modeled mesh.

    Returns
    -------
    pyvista.MultiBlock
        DataSet containing the high resolution forward modeled mesh
        and a coarse inverse modeled mesh.

    Examples
    --------
    >>> from pyvista import examples
    >>> fine, coarse = examples.download_tetra_dc_mesh()
    >>> coarse.plot()

    """
    local_path, _ = _download_file('dc-inversion.zip')
    local_path = os.path.join(local_path, 'dc-inversion')
    filename = os.path.join(local_path, 'mesh-forward.vtu')
    fwd = pyvista.read(filename)
    fwd.set_active_scalars('Resistivity(log10)-fwd')
    filename = os.path.join(local_path, 'mesh-inverse.vtu')
    inv = pyvista.read(filename)
    inv.set_active_scalars('Resistivity(log10)')
    return pyvista.MultiBlock({'forward': fwd, 'inverse': inv})


def download_model_with_variance(load=True):  # pragma: no cover
    """Download model with variance dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_model_with_variance()
    >>> dataset.plot()

    See :ref:`plot_opacity_example` for an example using this dataset.

    """
    return _download_and_read("model_with_variance.vtu", load=load)


def download_thermal_probes(load=True):  # pragma: no cover
    """Download thermal probes dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_thermal_probes()
    >>> dataset.plot(render_points_as_spheres=True, point_size=5, cpos="xy")

    See :ref:`interpolate_example` for an example using this dataset.

    """
    return _download_and_read("probes.vtp", load=load)


def download_carburator(load=True):  # pragma: no cover
    """Download scan of a carburator.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_carburator()
    >>> dataset.plot()

    """
    return _download_and_read("carburetor.ply", load=load)


def download_turbine_blade(load=True):  # pragma: no cover
    """Download scan of a turbine blade.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_turbine_blade()
    >>> dataset.plot()

    """
    return _download_and_read('turbineblade.ply', load=load)


def download_pine_roots(load=True):  # pragma: no cover
    """Download pine roots dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_pine_roots()
    >>> dataset.plot()

    See :ref:`connectivity_example` for an example using this dataset.

    """
    return _download_and_read('pine_root.tri', load=load)


def download_crater_topo(load=True):  # pragma: no cover
    """Download crater dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_crater_topo()
    >>> dataset.plot(cmap="gist_earth", cpos="xy")

    This dataset is used in the following examples:

    * :ref:`terrain_following_mesh_example`
    * :ref:`ref_topo_map_example`

    """
    return _download_and_read('Ruapehu_mag_dem_15m_NZTM.vtk', load=load)


def download_crater_imagery(load=True):  # pragma: no cover
    """Download crater texture.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.Texture or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> cpos = [
    ...     [  66.,  73. , -382.6],
    ...     [  66.,  73. ,    0. ],
    ...     [  -0.,  -1. ,    0. ]
    ... ]
    >>> dataset = examples.download_crater_imagery()
    >>> dataset.plot(cpos=cpos)

    See :ref:`ref_topo_map_example` for an example using this dataset.

    """
    return _download_and_read('BJ34_GeoTifv1-04_crater_clip.tif', texture=True, load=load)


def download_dolfin(load=True):  # pragma: no cover
    """Download dolfin mesh.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_dolfin()
    >>> dataset.plot(cpos="xy", show_edges=True)

    """
    return _download_and_read('dolfin_fine.xml', file_format="dolfin-xml", load=load)


def download_damavand_volcano(load=True):  # pragma: no cover
    """Download damavand volcano model.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> cpos = [
    ...     [ 4.66316700e+04,  4.32796241e+06, -3.82467050e+05],
    ...     [ 5.52532740e+05,  3.98017300e+06, -2.47450000e+04],
    ...     [ 4.10000000e-01, -2.90000000e-01, -8.60000000e-01]
    ... ]
    >>> dataset = examples.download_damavand_volcano()
    >>> dataset.plot(cpos=cpos, cmap="reds", show_scalar_bar=False, volume=True)

    See :ref:`volume_rendering_example` for an example using this dataset.

    """
    volume = _download_and_read("damavand-volcano.vtk", load=load)
    if not load:
        return volume
    volume.rename_array("None", "data")
    return volume


def download_delaunay_example(load=True):  # pragma: no cover
    """Download a pointset for the Delaunay example.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_delaunay_example()
    >>> dataset.plot(show_edges=True)

    """
    return _download_and_read('250.vtk', load=load)


def download_embryo(load=True):  # pragma: no cover
    """Download a volume of an embryo.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_embryo()
    >>> dataset.plot(volume=True)

    This dataset is used in the following examples:

    * :ref:`contouring_example`
    * :ref:`resampling_example`
    * :ref:`orthogonal_slices_example`

    """
    filename = _download_and_read('embryo.slc', load=False)
    if load:
        # cleanup artifact
        dataset = pyvista.read(filename)
        mask = dataset['SLCImage'] == 255
        dataset['SLCImage'][mask] = 0
        return dataset
    else:
        return filename


def download_antarctica_velocity(load=True):  # pragma: no cover
    """Download the antarctica velocity simulation results.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_antarctica_velocity()
    >>> dataset.plot(cpos='xy', clim=[1e-3, 1e4], cmap='Blues', log_scale=True)

    See :ref:`antarctica_example` for an example using this dataset.

    """
    return _download_and_read("antarctica_velocity.vtp", load=load)


def download_room_surface_mesh(load=True):  # pragma: no cover
    """Download the room surface mesh.

    This mesh is for demonstrating the difference that depth peeling can
    provide when rendering translucent geometries.

    This mesh is courtesy of `Sam Potter <https://github.com/sampotter>`_.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_room_surface_mesh()
    >>> dataset.plot()

    See :ref:`depth_peeling_example` for an example using this dataset.

    """
    return _download_and_read("room_surface_mesh.obj", load=load)


def download_beach(load=True):  # pragma: no cover
    """Download the beach NRRD image.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_beach()
    >>> dataset.plot(rgba=True, cpos="xy")

    """
    return _download_and_read("beach.nrrd", load=load)


def download_rgba_texture(load=True):  # pragma: no cover
    """Download a texture with an alpha channel.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.Texture or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_rgba_texture()
    >>> dataset.plot(cpos="xy")

    See :ref:`ref_texture_example` for an example using this dataset.

    """
    return _download_and_read("alphachannel.png", texture=True, load=load)


def download_vtk_logo(load=True):  # pragma: no cover
    """Download a texture of the VTK logo.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.Texture or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_vtk_logo()
    >>> dataset.plot(cpos="xy")

    """
    return _download_and_read("vtk.png", texture=True, load=load)


def download_sky_box_cube_map():  # pragma: no cover
    """Download a skybox cube map texture.

    Returns
    -------
    pyvista.Texture
        Texture containing a skybox.

    Examples
    --------
    >>> from pyvista import examples
    >>> import pyvista as pv
    >>> pl = pv.Plotter()
    >>> dataset = examples.download_sky_box_cube_map()
    >>> _ = pl.add_actor(dataset.to_skybox())
    >>> pl.set_environment_texture(dataset)
    >>> pl.show()

    See :ref:`pbr_example` for an example using this dataset.

    """
    prefix = 'skybox2-'
    sets = ['posx', 'negx', 'posy', 'negy', 'posz', 'negz']
    images = [prefix + suffix + '.jpg' for suffix in sets]
    for image in images:
        _download_file(image)

    return pyvista.cubemap(pyvista.EXAMPLES_PATH, prefix)


def download_cube_map_debug():  # pragma: no cover
    """Download the debug cube map texture.

    Textures obtained from `BabylonJS/Babylon.js
    <https://github.com/BabylonJS/Babylon.js>`_ and licensed under Apache2.

    Returns
    -------
    pyvista.Texture
        Texture containing a skybox.

    Examples
    --------
    >>> from pyvista import examples
    >>> import pyvista as pv
    >>> pl = pv.Plotter()
    >>> dataset = examples.download_sky_box_cube_map()
    >>> _ = pl.add_actor(dataset.to_skybox())
    >>> pl.set_environment_texture(dataset)
    >>> pl.show()

    """
    path, _ = _download_file('cubemapDebug/cubemapDebug.zip')
    return pyvista.cubemap(image_paths=glob.glob(path, '*.jpg'))


def download_cubemap_park():  # pragma: no cover
    """Download a cubemap of a park.

    Downloaded from http://www.humus.name/index.php?page=Textures
    by David Eck, and converted to a smaller 512x512 size for use
    with WebGL in his free, on-line textbook at
    http://math.hws.edu/graphicsbook

    This work is licensed under a Creative Commons Attribution 3.0 Unported
    License.

    Returns
    -------
    pyvista.Texture
        Texture containing a skybox.

    Examples
    --------
    >>> from pyvista import examples
    >>> import pyvista as pv
    >>> pl = pv.Plotter(lighting=None)
    >>> dataset = examples.download_cubemap_park()
    >>> _ = pl.add_actor(dataset.to_skybox())
    >>> pl.set_environment_texture(dataset, True)
    >>> pl.camera_position = 'xy'
    >>> pl.camera.zoom(0.4)
    >>> _ = pl.add_mesh(pv.Sphere(), pbr=True, roughness=0.1, metallic=0.5)
    >>> pl.show()

    """
    path, _ = _download_file('cubemap_park/cubemap_park.zip')
    return pyvista.cubemap(path)


def download_cubemap_space_4k():  # pragma: no cover
    """Download the 4k space cubemap.

    This cubemap was generated by downloading the 4k image from: `Deep Star
    Maps 2020 <https://svs.gsfc.nasa.gov/4851>`_ and converting it using
    https://jaxry.github.io/panorama-to-cubemap/

    See `vtk-data/Data/cubemap_space
    <https://github.com/pyvista/vtk-data/tree/master/Data/cubemap_space>`_ for
    more details.

    Returns
    -------
    pyvista.Texture
        Texture containing a skybox.

    Examples
    --------
    Display the cubemap as both an environment texture and an actor.

    >>> import pyvista as pv
    >>> from pyvista import examples
    >>> cubemap = examples.download_cubemap_space_4k()
    >>> pl = pv.Plotter(lighting=None)
    >>> _ = pl.add_actor(cubemap.to_skybox())
    >>> pl.set_environment_texture(cubemap, True)
    >>> pl.camera.zoom(0.4)
    >>> _ = pl.add_mesh(pv.Sphere(), pbr=True, roughness=0.24, metallic=1.0)
    >>> pl.show()

    """
    path, _ = _download_file('cubemap_space/4k.zip')
    return pyvista.cubemap(path)


def download_cubemap_space_16k(progress_bar=False):  # pragma: no cover
    """Download the 16k space cubemap.

    This cubemap was generated by downloading the 16k image from: `Deep Star
    Maps 2020 <https://svs.gsfc.nasa.gov/4851>`_ and converting it using
    https://jaxry.github.io/panorama-to-cubemap/

    See `vtk-data/Data/cubemap_space
    <https://github.com/pyvista/vtk-data/tree/master/Data/cubemap_space>`_ for
    more details.

    Parameters
    ----------
    progress_bar : bool, default: False
        Display a progress_bar bar when downloading the file. Requires ``tqdm``.


    Returns
    -------
    pyvista.Texture
        Texture containing a skybox.

    Notes
    -----
    This is a 38MB file and may take a while to download.

    Examples
    --------
    Display the cubemap as both an environment texture and an actor. Note that
    here we're displaying the 4k as the 16k is a bit too expensive to display
    in the documentation.

    >>> import pyvista as pv
    >>> from pyvista import examples
    >>> cubemap = examples.download_cubemap_space_4k()
    >>> pl = pv.Plotter(lighting=None)
    >>> _ = pl.add_actor(cubemap.to_skybox())
    >>> pl.set_environment_texture(cubemap, True)
    >>> pl.camera.zoom(0.4)
    >>> _ = pl.add_mesh(pv.Sphere(), pbr=True, roughness=0.24, metallic=1.0)
    >>> pl.show()

    """
    path, _ = _download_file('cubemap_space/16k.zip', progress_bar=progress_bar)
    return pyvista.cubemap(path)


def download_backward_facing_step(load=True):  # pragma: no cover
    """Download an ensight gold case of a fluid simulation.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.MultiBlock or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_backward_facing_step()
    >>> dataset.plot()

    """
    directory, _ = _download_file('EnSight.zip')
    filename = os.path.join(directory, 'EnSight', "foam_case_0_0_0_0.case")
    if not load:
        return filename
    return pyvista.read(filename)


def download_gpr_data_array(load=True):  # pragma: no cover
    """Download GPR example data array.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    numpy.ndarray or str
        Array or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_gpr_data_array()  # doctest:+SKIP
    >>> dataset  # doctest:+SKIP
    array([[nan, nan, nan, ..., nan, nan, nan],
           [nan, nan, nan, ..., nan, nan, nan],
           [nan, nan, nan, ..., nan, nan, nan],
           ...,
           [ 0.,  0.,  0., ...,  0.,  0.,  0.],
           [ 0.,  0.,  0., ...,  0.,  0.,  0.],
           [ 0.,  0.,  0., ...,  0.,  0.,  0.]])

    See :ref:`create_draped_surf_example` for an example using this dataset.

    """
    saved_file, _ = _download_file("gpr-example/data.npy")
    if not load:
        return saved_file
    return np.load(saved_file)


def download_gpr_path(load=True):  # pragma: no cover
    """Download GPR example path.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_gpr_path()
    >>> dataset.plot()

    See :ref:`create_draped_surf_example` for an example using this dataset.

    """
    saved_file, _ = _download_file("gpr-example/path.txt")
    if not load:
        return saved_file
    path = np.loadtxt(saved_file, skiprows=1)
    return pyvista.PolyData(path)


def download_woman(load=True):  # pragma: no cover
    """Download scan of a woman.

    Originally obtained from Laser Design.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_woman()
    >>> cpos = [
    ...     (-2600.0, 1970.6, 1836.9),
    ...     (48.5, -20.3, 843.9),
    ...     (0.23, -0.168, 0.958)
    ... ]
    >>> dataset.plot(cpos=cpos)

    """
    return _download_and_read('woman.stl', load=load)


def download_lobster(load=True):  # pragma: no cover
    """Download scan of a lobster.

    Originally obtained from Laser Design.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_lobster()
    >>> dataset.plot()

    """
    return _download_and_read('lobster.ply', load=load)


def download_face2(load=True):  # pragma: no cover
    """Download scan of a man's face.

    Originally obtained from Laser Design.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_face2()
    >>> dataset.plot()

    """
    return _download_and_read('man_face.stl', load=load)


def download_urn(load=True):  # pragma: no cover
    """Download scan of a burial urn.

    Originally obtained from Laser Design.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> cpos = [
    ...     [-7.123e+02,  5.715e+02,  8.601e+02],
    ...     [ 4.700e+00,  2.705e+02, -1.010e+01],
    ...     [ 2.000e-01,  1.000e+00, -2.000e-01]
    ... ]
    >>> dataset = examples.download_urn()
    >>> dataset.plot(cpos=cpos)

    """
    return _download_and_read('urn.stl', load=load)


def download_pepper(load=True):  # pragma: no cover
    """Download scan of a pepper (capsicum).

    Originally obtained from Laser Design.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_pepper()
    >>> dataset.plot()

    """
    return _download_and_read('pepper.ply', load=load)


def download_drill(load=True):  # pragma: no cover
    """Download scan of a power drill.

    Originally obtained from Laser Design.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_drill()
    >>> dataset.plot()

    """
    return _download_and_read('drill.obj', load=load)


def download_action_figure(load=True):  # pragma: no cover
    """Download scan of an action figure.

    Originally obtained from Laser Design.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Show the action figure example. This also demonstrates how to use
    physically based rendering and lighting to make a good looking
    plot.

    >>> import pyvista
    >>> from pyvista import examples
    >>> dataset = examples.download_action_figure()
    >>> _ = dataset.clean(inplace=True)
    >>> pl = pyvista.Plotter(lighting=None)
    >>> pl.add_light(pyvista.Light((30, 10, 10)))
    >>> _ = pl.add_mesh(dataset, color='w', smooth_shading=True,
    ...                 pbr=True, metallic=0.3, roughness=0.5)
    >>> pl.camera_position = [
    ...     (32.3, 116.3, 220.6),
    ...     (-0.05, 3.8, 33.8),
    ...     (-0.017, 0.86, -0.51)
    ... ]
    >>> pl.show()

    """
    return _download_and_read('tigerfighter.obj', load=load)


def download_mars_jpg():  # pragma: no cover
    """Download and return the path of ``'mars.jpg'``.

    Returns
    -------
    str
        Filename of the JPEG.

    Examples
    --------
    Download the Mars JPEG and map it to spherical coordinates on a sphere.

    >>> import math
    >>> import numpy
    >>> import numpy as np
    >>> from pyvista import examples
    >>> import pyvista

    Download the JPEGs and convert the Mars JPEG to a texture.

    >>> mars_jpg = examples.download_mars_jpg()
    >>> mars_tex = pyvista.read_texture(mars_jpg)
    >>> stars_jpg = examples.download_stars_jpg()

    Create a sphere mesh and compute the texture coordinates.

    >>> sphere = pyvista.Sphere(radius=1, theta_resolution=120, phi_resolution=120,
    ...                         start_theta=270.001, end_theta=270)
    >>> sphere.active_t_coords = numpy.zeros((sphere.points.shape[0], 2))
    >>> sphere.active_t_coords[:, 0] = 0.5 + np.arctan2(-sphere.points[:, 0],
    ...                                                 sphere.points[:, 1])/(2 * math.pi)
    >>> sphere.active_t_coords[:, 1] = 0.5 + np.arcsin(sphere.points[:, 2]) / math.pi
    >>> sphere.point_data
    pyvista DataSetAttributes
    Association     : POINT
    Active Scalars  : None
    Active Vectors  : None
    Active Texture  : Texture Coordinates
    Active Normals  : Normals
    Contains arrays :
        Normals                 float32    (14280, 3)           NORMALS
        Texture Coordinates     float64    (14280, 2)           TCOORDS

    Plot with stars in the background.

    >>> pl = pyvista.Plotter()
    >>> pl.add_background_image(stars_jpg)
    >>> _ = pl.add_mesh(sphere, texture=mars_tex)
    >>> pl.show()

    """
    return _download_file('mars.jpg')[0]


def download_stars_jpg():  # pragma: no cover
    """Download and return the path of ``'stars.jpg'``.

    Returns
    -------
    str
        Filename of the JPEG.

    Examples
    --------
    >>> from pyvista import examples
    >>> import pyvista as pv
    >>> pl = pv.Plotter()
    >>> dataset = examples.download_stars_jpg()
    >>> pl.add_background_image(dataset)
    >>> pl.show()

    See :func:`download_mars_jpg` for another example using this dataset.

    """
    return _download_file('stars.jpg')[0]


def download_notch_stress(load=True):  # pragma: no cover
    """Download the FEA stress result from a notched beam.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Notes
    -----
    This file may have issues being read in on VTK 8.1.2

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_notch_stress()
    >>> dataset.plot(cmap='bwr')

    """
    return _download_and_read('notch_stress.vtk', load=load)


def download_notch_displacement(load=True):  # pragma: no cover
    """Download the FEA displacement result from a notched beam.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_notch_displacement()
    >>> dataset.plot(cmap='bwr')

    """
    return _download_and_read('notch_disp.vtu', load=load)


def download_louis_louvre(load=True):  # pragma: no cover
    """Download the Louis XIV de France statue at the Louvre, Paris.

    Statue found in the Napoléon Courtyard of Louvre Palace. It is a
    copy in plomb of the original statue in Versailles, made by
    Bernini and Girardon.

    Originally downloaded from `sketchfab <https://sketchfab.com/3d-models/louis-xiv-de-france-louvre-paris-a0cc0e7eee384c99838dff2857b8158c>`_

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Plot the Louis XIV statue with custom lighting and camera angle.

    >>> from pyvista import examples
    >>> import pyvista
    >>> dataset = examples.download_louis_louvre()
    >>> pl = pyvista.Plotter(lighting=None)
    >>> _ = pl.add_mesh(dataset, smooth_shading=True)
    >>> pl.add_light(pyvista.Light((10, -10, 10)))
    >>> pl.camera_position = [
    ...     [ -6.71, -14.55,  15.17],
    ...     [  1.44,   2.54,   9.84],
    ...     [  0.16,   0.22,   0.96]
    ... ]
    >>> pl.show()

    See :ref:`pbr_example` for an example using this dataset.

    """
    return _download_and_read('louis.ply', load=load)


def download_cylinder_crossflow(load=True):  # pragma: no cover
    """Download CFD result for cylinder in cross flow at Re=35.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.MultiBlock or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_cylinder_crossflow()
    >>> dataset.plot(cpos='xy', cmap='blues', rng=[-200, 500])

    See :ref:`2d_streamlines_example` for an example using this dataset.

    """
    filename, _ = _download_file('EnSight/CylinderCrossflow/cylinder_Re35.case')
    _download_file('EnSight/CylinderCrossflow/cylinder_Re35.geo')
    _download_file('EnSight/CylinderCrossflow/cylinder_Re35.scl1')
    _download_file('EnSight/CylinderCrossflow/cylinder_Re35.scl2')
    _download_file('EnSight/CylinderCrossflow/cylinder_Re35.vel')
    if not load:
        return filename
    return pyvista.read(filename)


def download_naca(load=True):  # pragma: no cover
    """Download NACA airfoil dataset in EnSight format.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.MultiBlock or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Plot the density of the air surrounding the NACA airfoil using the
    ``"jet"`` color map.

    >>> from pyvista import examples
    >>> cpos = [
    ...     [-0.22,  0.  ,  2.52],
    ...     [ 0.43,  0.  ,  0.  ],
    ...     [ 0.  ,  1.  ,  0.  ]
    ... ]
    >>> dataset = examples.download_naca()
    >>> dataset.plot(cpos=cpos, cmap="jet")

    See :ref:`reader_example` for an example using this dataset.

    """
    filename, _ = _download_file('EnSight/naca.bin.case')
    _download_file('EnSight/naca.gold.bin.DENS_1')
    _download_file('EnSight/naca.gold.bin.DENS_3')
    _download_file('EnSight/naca.gold.bin.geo')
    if not load:
        return filename
    return pyvista.read(filename)


def download_wavy(load=True):  # pragma: no cover
    """Download PVD file of a 2D wave.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.MultiBlock or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_wavy()
    >>> dataset.plot()

    See :ref:`reader_example` for an example using this dataset.

    """
    folder, _ = _download_file('PVD/wavy.zip')
    filename = os.path.join(folder, 'wavy.pvd')
    if not load:
        return filename
    return pyvista.PVDReader(filename).read()


def download_single_sphere_animation(load=True):  # pragma: no cover
    """Download PVD file for single sphere.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.MultiBlock or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> import os
    >>> from tempfile import mkdtemp
    >>> import pyvista
    >>> from pyvista import examples
    >>> filename = examples.download_single_sphere_animation(load=False)
    >>> reader = pyvista.PVDReader(filename)

    Write the gif to a temporary directory. Normally you would write to a local
    path.

    >>> gif_filename = os.path.join(mkdtemp(), 'single_sphere.gif')

    Generate the animation.

    >>> plotter = pyvista.Plotter()
    >>> plotter.open_gif(gif_filename)
    >>> for time_value in reader.time_values:
    ...     reader.set_active_time_value(time_value)
    ...     mesh = reader.read()
    ...     _ = plotter.add_mesh(mesh, smooth_shading=True)
    ...     _ = plotter.add_text(f"Time: {time_value:.0f}", color="black")
    ...     plotter.write_frame()
    ...     plotter.clear()
    ...     plotter.enable_lightkit()
    >>> plotter.close()

    """
    path, _ = _download_file('PVD/paraview/singleSphereAnimation.zip')
    filename = os.path.join(path, 'singleSphereAnimation.pvd')
    if not load:
        return filename
    return pyvista.PVDReader(filename).read()


def download_dual_sphere_animation(load=True):  # pragma: no cover
    """Download PVD file for double sphere.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.MultiBlock or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> import os
    >>> from tempfile import mkdtemp
    >>> import pyvista
    >>> from pyvista import examples
    >>> filename = examples.download_dual_sphere_animation(load=False)
    >>> reader = pyvista.PVDReader(filename)

    Write the gif to a temporary directory. Normally you would write to a local
    path.

    >>> gif_filename = os.path.join(mkdtemp(), 'dual_sphere.gif')

    Generate the animation.

    >>> plotter = pyvista.Plotter()
    >>> plotter.open_gif(gif_filename)
    >>> for time_value in reader.time_values:
    ...     reader.set_active_time_value(time_value)
    ...     mesh = reader.read()
    ...     _ = plotter.add_mesh(mesh, smooth_shading=True)
    ...     _ = plotter.add_text(f"Time: {time_value:.0f}", color="black")
    ...     plotter.write_frame()
    ...     plotter.clear()
    ...     plotter.enable_lightkit()
    >>> plotter.close()

    """
    path, _ = _download_file('PVD/paraview/dualSphereAnimation.zip')
    filename = os.path.join(path, 'dualSphereAnimation.pvd')
    if not load:
        return filename
    return pyvista.PVDReader(filename).read()


def download_osmnx_graph():  # pragma: no cover
    """Load a simple street map from Open Street Map.

    Generated from:

    .. code:: python

        >>> import osmnx as ox  # doctest:+SKIP
        >>> address = 'Holzgerlingen DE'  # doctest:+SKIP
        >>> graph = ox.graph_from_address(address, dist=500, network_type='drive')  # doctest:+SKIP
        >>> pickle.dump(graph, open('osmnx_graph.p', 'wb'))  # doctest:+SKIP

    Returns
    -------
    networkx.classes.multidigraph.MultiDiGraph
        An osmnx graph of the streets of Holzgerlingen, Germany.

    Examples
    --------
    >>> from pyvista import examples
    >>> graph = examples.download_osmnx_graph()  # doctest:+SKIP

    See :ref:`open_street_map_example` for a full example using this dataset.

    """
    import pickle

    try:
        import osmnx  # noqa
    except ImportError:
        raise ImportError('Install `osmnx` to use this example')

    filename, _ = _download_file('osmnx_graph.p')
    return pickle.load(open(filename, 'rb'))


def download_cavity(load=True):
    """Download cavity OpenFOAM example.

    Retrieved from
    `Kitware VTK Data <https://data.kitware.com/#collection/55f17f758d777f6ddc7895b7/folder/5afd932e8d777f15ebe1b183>`_.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.MultiBlock or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_cavity()  # doctest:+SKIP

    See :ref:`openfoam_example` for a full example using this dataset.

    """
    directory, _ = _download_file('OpenFOAM.zip')
    filename = os.path.join(directory, 'OpenFOAM', 'cavity', 'case.foam')
    if not load:
        return filename
    return pyvista.OpenFOAMReader(filename).read()


def download_lucy(load=True):  # pragma: no cover
    """Download the lucy angel mesh.

    Original downloaded from the `The Stanford 3D Scanning Repository
    <http://graphics.stanford.edu/data/3Dscanrep/>`_ and decimated to
    approximately 100k triangle.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Plot the Lucy Angel dataset with custom lighting.

    >>> from pyvista import examples
    >>> import pyvista
    >>> dataset = examples.download_lucy()

    Create a light at the "flame"

    >>> flame_light = pyvista.Light(
    ...     color=[0.886, 0.345, 0.133],
    ...     position=[550,  140, 950],
    ...     intensity=1.5,
    ...     positional=True,
    ...     cone_angle=90,
    ...     attenuation_values=(0.001, 0.005, 0)
    ... )

    Create a scene light

    >>> scene_light = pyvista.Light(intensity=0.2)

    >>> pl = pyvista.Plotter(lighting=None)
    >>> _ = pl.add_mesh(dataset, smooth_shading=True)
    >>> pl.add_light(flame_light)
    >>> pl.add_light(scene_light)
    >>> pl.background_color = 'k'
    >>> pl.show()

    See :ref:`jupyter_plotting` for another example using this dataset.

    """
    return _download_and_read('lucy.ply', load=load)


def download_can(partial=False, load=True):  # pragma: no cover
    """Download the can dataset mesh.

    File obtained from `Kitware <https://www.kitware.com/>`_. Used
    for testing hdf files.

    Parameters
    ----------
    partial : bool, optional
        Load part of the dataset. Defaults to ``False``.

    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData, str, or List[str]
        The example ParaView can DataSet or file path(s).

    Examples
    --------
    Plot the can dataset.

    >>> from pyvista import examples
    >>> import pyvista
    >>> dataset = examples.download_can()  # doctest:+SKIP
    >>> dataset.plot(scalars='VEL', smooth_shading=True)  # doctest:+SKIP

    """
    if pyvista.vtk_version_info > (9, 1):
        raise VTKVersionError(
            'This example file is deprecated for VTK v9.2.0 and newer. '
            'Use `download_can_crushed_hdf` instead.'
        )

    can_0 = _download_and_read('hdf/can_0.hdf', load=load)
    if partial:
        return can_0

    cans = [
        can_0,
        _download_and_read('hdf/can_1.hdf', load=load),
        _download_and_read('hdf/can_2.hdf', load=load),
    ]

    if load:
        return pyvista.merge(cans)
    return cans


def download_can_crushed_hdf(load=True):  # pragma: no cover
    """Download the crushed can dataset.

    File obtained from `Kitware <https://www.kitware.com/>`_. Used
    for testing hdf files.

    Originally built using VTK v9.2.0rc from:

    ``VTK/build/ExternalData/Testing/Data/can-vtu.hdf``

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        Crushed can dataset or path depending on the value of ``load``.

    Examples
    --------
    Plot the crushed can dataset.

    >>> from pyvista import examples
    >>> import pyvista
    >>> dataset = examples.download_can_crushed_hdf()
    >>> dataset.plot(smooth_shading=True)

    """
    return _download_and_read('hdf/can-vtu.hdf', load=load)


def download_cgns_structured(load=True):  # pragma: no cover
    """Download the structured CGNS dataset mesh.

    Originally downloaded from `CFD General Notation System Example Files
    <https://cgns.github.io/CGNSFiles.html>`_

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.MultiBlock or str
        Structured, 12 block, 3-D constricting channel, with example use of
        Family_t for BCs (ADF type). If ``load`` is ``False``, then the path of the
        example CGNS file is returned.

    Examples
    --------
    Plot the example CGNS dataset.

    >>> from pyvista import examples
    >>> import pyvista
    >>> dataset = examples.download_cgns_structured()
    >>> dataset[0].plot(scalars='Density')

    """
    filename, _ = _download_file('cgns/sqnz_s.adf.cgns')
    if not load:
        return filename
    return pyvista.get_reader(filename).read()


def download_tecplot_ascii(load=True):  # pragma: no cover
    """Download the single block ASCII Tecplot dataset.

    Originally downloaded from Paul Bourke's
    `Sample file <http://paulbourke.net/dataformats/tp/sample.tp>`_

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.MultiBlock
        Multiblock format with only 1 data block, simple geometric shape.
        If ``load`` is ``False``, then the path of the example Tecplot file
        is returned.

    Examples
    --------
    Plot the example Tecplot dataset.

    >>> from pyvista import examples
    >>> import pyvista
    >>> dataset = examples.download_tecplot_ascii()
    >>> dataset.plot()

    """
    filename, _ = _download_file('tecplot_ascii.dat')
    if not load:
        return filename
    return pyvista.get_reader(filename).read()


def download_cgns_multi(load=True):  # pragma: no cover
    """Download a multielement airfoil with a cell centered solution.

    Originally downloaded from `CFD General Notation System Example Files
    <https://cgns.github.io/CGNSFiles.html>`_

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.MultiBlock or str
        Structured, 4 blocks, 2D (2 planes in third dimension) multielement
        airfoil, with cell centered solution. If ``load`` is ``False``, then the path of the
        example CGNS file is returned.

    Examples
    --------
    Plot the airfoil dataset. Merge the multi-block and then plot the airfoil's
    ``"ViscosityEddy"``. Convert the cell data to point data as in this
    dataset, the solution is stored within the cells.

    >>> from pyvista import examples
    >>> import pyvista
    >>> dataset = examples.download_cgns_multi()
    >>> ugrid = dataset.combine()
    >>> ugrid = ugrid = ugrid.cell_data_to_point_data()
    >>> ugrid.plot(
    ...     cmap='bwr', scalars='ViscosityEddy', zoom=4, cpos='xz', show_scalar_bar=False,
    ... )

    """
    filename, _ = _download_file('cgns/multi.cgns')
    if not load:
        return filename
    reader = pyvista.get_reader(filename)

    # disable reading the boundary patch. As of VTK 9.1.0 this generates
    # messages like "Skipping BC_t node: BC_t type 'BCFarfield' not supported
    # yet."
    reader.load_boundary_patch = False
    return reader.read()


def download_dicom_stack(load: bool = True) -> Union[pyvista.UniformGrid, str]:  # pragma: no cover
    """Download TCIA DICOM stack volume.

    Original download from the `The Cancer Imaging Archive (TCIA)
    <https://www.cancerimagingarchive.net/>`_. This is part of the
    Clinical Proteomic Tumor Analysis Consortium Sarcomas (CPTAC-SAR)
    collection.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    References
    ----------
    * **Data Citation**

        National Cancer Institute Clinical Proteomic Tumor Analysis Consortium
        (CPTAC). (2018).  Radiology Data from the Clinical Proteomic Tumor
        Analysis Consortium Sarcomas [CPTAC-SAR] collection [Data set]. The
        Cancer Imaging Archive.  DOI: 10.7937/TCIA.2019.9bt23r95

    * **Acknowledgement**

        Data used in this publication were generated by the National Cancer Institute Clinical
        Proteomic Tumor Analysis Consortium (CPTAC).

    * **TCIA Citation**

        Clark K, Vendt B, Smith K, Freymann J, Kirby J, Koppel P, Moore S, Phillips S,
        Maffitt D, Pringle M, Tarbox L, Prior F. The Cancer Imaging Archive (TCIA):
        Maintaining and Operating a Public Information Repository, Journal of Digital Imaging,
        Volume 26, Number 6, December, 2013, pp 1045-1057. doi: 10.1007/s10278-013-9622-7

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_dicom_stack()
    >>> dataset.plot(volume=True, zoom=3, show_scalar_bar=False)

    """
    path, _ = _download_file('DICOM_Stack/data.zip')
    path = os.path.join(path, 'data')
    if load:
        reader = pyvista.DICOMReader(path)
        return reader.read()
    return path


def download_parched_canal_4k(load=True):  # pragma: no cover
    """Download parched canal 4k dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.Texture or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_parched_canal_4k()
    >>> dataset.plot(cpos="xy")

    """
    return _download_and_read("parched_canal_4k.hdr", texture=True, load=load)


def download_cells_nd(load=True):  # pragma: no cover
    """Download example AVS UCD dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.DataSet or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_cells_nd()
    >>> dataset.plot(cpos="xy")

    """
    return _download_and_read("cellsnd.ascii.inp", load=load)


def download_moonlanding_image(load=True):  # pragma: no cover
    """Download the Moon landing image.

    This is a noisy image originally obtained from `Scipy Lecture Notes
    <https://scipy-lectures.org/index.html>`_ and can be used to demonstrate a
    low pass filter.

    See the `scipy-lectures license
    <http://scipy-lectures.org/preface.html#license>`_ for more details
    regarding this image's use and distribution.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        ``DataSet`` or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_moonlanding_image()
    >>> dataset.plot(cpos='xy', cmap='gray', background='w', show_scalar_bar=False)

    See :ref:`image_fft_example` for a full example using this dataset.

    """
    return _download_and_read('moonlanding.png', load=load)


def download_angular_sector(load=True):  # pragma: no cover
    """Download the angular sector dataset.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    >>> from pyvista import examples
    >>> dataset = examples.download_angular_sector()
    >>> dataset.plot(scalars='PointId')

    """
    return _download_and_read('AngularSector.vtk', load=load)


def download_mount_damavand(load=True):  # pragma: no cover
    """Download the Mount Damavand dataset.

    Visualize 3D models of Damavand Volcano, Alborz, Iran. This is a 2D map
    with the altitude embedded as ``'z'`` cell data within the
    :class:`pyvista.PolyData`.

    Originally posted at `banesullivan/damavand-volcano
    <https://github.com/banesullivan/damavand-volcano>`_.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Download the Damavand dataset and plot it after warping it by its altitude.

    >>> from pyvista import examples
    >>> dataset = examples.download_mount_damavand()
    >>> dataset = dataset.cell_data_to_point_data()
    >>> dataset = dataset.warp_by_scalar('z', factor=2)
    >>> dataset.plot(cmap='gist_earth', show_scalar_bar=False)

    """
    return _download_and_read('AOI.Damavand.32639.vtp', load=load)


def download_particles_lethe(load=True):  # pragma: no cover
    """Download a particles dataset generated by `lethe <https://github.com/lethe-cfd/lethe>`_ .

    See `PyVista discussions #1984
    <https://github.com/pyvista/pyvista/discussions/1984>`_

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UnstructuredGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Download the particles dataset and plot it after generating glyphs.

    >>> from pyvista import examples
    >>> particles = examples.download_particles_lethe()
    >>> particles.plot(
    ...     render_points_as_spheres=True,
    ...     style='points',
    ...     scalars='Velocity',
    ...     background='w',
    ...     scalar_bar_args={'color': 'k'},
    ...     cmap='bwr'
    ... )

    """
    return _download_and_read('lethe/result_particles.20000.0000.vtu', load=load)


def download_gif_simple(load=True):  # pragma: no cover
    """Download a simple three frame GIF.

    Parameters
    ----------
    load : bool, optional
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    Returns
    -------
    pyvista.UniformGrid or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Download and plot the first frame of a simple GIF.

    >>> from pyvista import examples
    >>> grid = examples.download_gif_simple()
    >>> grid.plot(
    ...     scalars='frame0',
    ...     rgb=True,
    ...     background='w',
    ...     show_scalar_bar=False,
    ...     cpos='xy'
    ... )

    Plot the second frame.

    >>> grid.plot(
    ...     scalars='frame1',
    ...     rgb=True,
    ...     background='w',
    ...     show_scalar_bar=False,
    ...     cpos='xy'
    ... )

    """
    return _download_and_read('gifs/sample.gif', load=load)


def download_black_vase(load=True, progress_bar=False):  # pragma: no cover
    """Download a black vase scan created by Ivan Nikolov.

    The dataset was downloaded from `GGG-BenchmarkSfM: Dataset for Benchmarking
    Close-range SfM Software Performance under Varying Capturing Conditions
    <https://data.mendeley.com/datasets/bzxk2n78s9/4>`_

    Original datasets are under the CC BY 4.0 license.

    For more details, see `Ivan Nikolov Datasets
    <https://github.com/pyvista/vtk-data/tree/master/Data/ivan-nikolov>`_

    Parameters
    ----------
    load : bool, default: True
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    progress_bar : bool, default: False
        Display a progress_bar bar when downloading the file. Requires ``tqdm``.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Download and plot the dataset.

    >>> from pyvista import examples
    >>> mesh = examples.download_black_vase()
    >>> mesh.plot()

    Return the statistics of the dataset.

    >>> mesh  # doctest:+SKIP
    PolyData (0x7fe489493520)
      N Cells:      3136652
      N Points:     1611789
      X Bounds:     -1.092e+02, 1.533e+02
      Y Bounds:     -1.200e+02, 1.415e+02
      Z Bounds:     1.666e+01, 4.077e+02
      N Arrays:     0

    """
    path, _ = _download_file('ivan-nikolov/blackVase.zip', progress_bar=progress_bar)
    filename = os.path.join(path, 'blackVase.vtp')
    if load:
        return pyvista.read(filename)
    return filename


def download_ivan_angel(load=True, progress_bar=False):  # pragma: no cover
    """Download a scan of an angel statue created by Ivan Nikolov.

    The dataset was downloaded from `GGG-BenchmarkSfM: Dataset for Benchmarking
    Close-range SfM Software Performance under Varying Capturing Conditions
    <https://data.mendeley.com/datasets/bzxk2n78s9/4>`_

    Original datasets are under the CC BY 4.0 license.

    For more details, see `Ivan Nikolov Datasets
    <https://github.com/pyvista/vtk-data/tree/master/Data/ivan-nikolov>`_

    Parameters
    ----------
    load : bool, default: True
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    progress_bar : bool, default: False
        Display a progress_bar bar when downloading the file. Requires ``tqdm``.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Download and plot the dataset.

    >>> from pyvista import examples
    >>> mesh = examples.download_ivan_angel()
    >>> cpos = [(-476.14, -393.73, 282.14),
    ...         (-15.00, 11.25, 44.08),
    ...         (0.26, 0.24, 0.93)]
    >>> mesh.plot(cpos=cpos)

    Return the statistics of the dataset.

    >>> mesh  # doctest:+SKIP
    PolyData (0x7f6ed1345520)
      N Cells:      4547716
      N Points:     2297089
      X Bounds:     -1.147e+02, 8.468e+01
      Y Bounds:     -7.103e+01, 9.247e+01
      Z Bounds:     -1.198e+02, 2.052e+02
      N Arrays:     0

    """
    path, _ = _download_file('ivan-nikolov/Angel.zip', progress_bar=progress_bar)
    filename = os.path.join(path, 'Angel.vtp')
    if load:
        return pyvista.read(filename)
    return filename


def download_bird_bath(load=True, progress_bar=False):  # pragma: no cover
    """Download a scan of a bird bath created by Ivan Nikolov.

    The dataset was downloaded from `GGG-BenchmarkSfM: Dataset for Benchmarking
    Close-range SfM Software Performance under Varying Capturing Conditions
    <https://data.mendeley.com/datasets/bzxk2n78s9/4>`_

    Original datasets are under the CC BY 4.0 license.

    For more details, see `Ivan Nikolov Datasets
    <https://github.com/pyvista/vtk-data/tree/master/Data/ivan-nikolov>`_

    Parameters
    ----------
    load : bool, default: True
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    progress_bar : bool, default: False
        Display a progress_bar bar when downloading the file. Requires ``tqdm``.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Download and plot the dataset.

    >>> from pyvista import examples
    >>> mesh = examples.download_bird_bath()
    >>> mesh.plot()

    Return the statistics of the dataset.

    >>> mesh  # doctest:+SKIP
    PolyData (0x7fe8caf2ba00)
    N Cells:      3507935
    N Points:     1831383
    X Bounds:     -1.601e+02, 1.483e+02
    Y Bounds:     -1.521e+02, 1.547e+02
    Z Bounds:     -4.241e+00, 1.409e+02
    N Arrays:     0

    """
    path, _ = _download_file('ivan-nikolov/birdBath.zip', progress_bar=progress_bar)
    filename = os.path.join(path, 'birdBath.vtp')
    if load:
        return pyvista.read(filename)
    return filename


def download_owl(load=True, progress_bar=False):  # pragma: no cover
    """Download a scan of an owl statue created by Ivan Nikolov.

    The dataset was downloaded from `GGG-BenchmarkSfM: Dataset for Benchmarking
    Close-range SfM Software Performance under Varying Capturing Conditions
    <https://data.mendeley.com/datasets/bzxk2n78s9/4>`_

    Original datasets are under the CC BY 4.0 license.

    For more details, see `Ivan Nikolov Datasets
    <https://github.com/pyvista/vtk-data/tree/master/Data/ivan-nikolov>`_

    Parameters
    ----------
    load : bool, default: True
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    progress_bar : bool, default: False
        Display a progress_bar bar when downloading the file. Requires ``tqdm``.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Download and plot the dataset.

    >>> from pyvista import examples
    >>> mesh = examples.download_owl()
    >>> cpos = [(-315.18, -402.21, 230.71),
    ...         (6.06, -1.74, 101.48),
    ...         (0.108, 0.226, 0.968)]
    >>> mesh.plot(cpos=cpos)

    Return the statistics of the dataset.

    >>> mesh  # doctest:+SKIP
    PolyData (0x7fe8caeeaee0)
      N Cells:      2440707
      N Points:     1221756
      X Bounds:     -5.834e+01, 7.047e+01
      Y Bounds:     -7.006e+01, 6.658e+01
      Z Bounds:     1.676e+00, 2.013e+02
      N Arrays:     0

    """
    path, _ = _download_file('ivan-nikolov/owl.zip', progress_bar=progress_bar)
    filename = os.path.join(path, 'owl.vtp')
    if load:
        return pyvista.read(filename)
    return filename


def download_plastic_vase(load=True, progress_bar=False):  # pragma: no cover
    """Download a scan of a plastic vase created by Ivan Nikolov.

    The dataset was downloaded from `GGG-BenchmarkSfM: Dataset for Benchmarking
    Close-range SfM Software Performance under Varying Capturing Conditions
    <https://data.mendeley.com/datasets/bzxk2n78s9/4>`_

    Original datasets are under the CC BY 4.0 license.

    For more details, see `Ivan Nikolov Datasets
    <https://github.com/pyvista/vtk-data/tree/master/Data/ivan-nikolov>`_

    Parameters
    ----------
    load : bool, default: True
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    progress_bar : bool, default: False
        Display a progress_bar bar when downloading the file. Requires ``tqdm``.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Download and plot the dataset.

    >>> from pyvista import examples
    >>> mesh = examples.download_plastic_vase()
    >>> mesh.plot()

    Return the statistics of the dataset.

    >>> mesh  # doctest:+SKIP
    PolyData (0x7fe8cadc14c0)
      N Cells:      3570967
      N Points:     1796805
      X Bounds:     -1.364e+02, 1.929e+02
      Y Bounds:     -1.677e+02, 1.603e+02
      Z Bounds:     1.209e+02, 4.090e+02
      N Arrays:     0

    """
    path, _ = _download_file('ivan-nikolov/plasticVase.zip', progress_bar=progress_bar)
    filename = os.path.join(path, 'plasticVase.vtp')
    if load:
        return pyvista.read(filename)
    return filename


def download_sea_vase(load=True, progress_bar=False):  # pragma: no cover
    """Download a scan of a sea vase created by Ivan Nikolov.

    The dataset was downloaded from `GGG-BenchmarkSfM: Dataset for Benchmarking
    Close-range SfM Software Performance under Varying Capturing Conditions
    <https://data.mendeley.com/datasets/bzxk2n78s9/4>`_

    Original datasets are under the CC BY 4.0 license.

    For more details, see `Ivan Nikolov Datasets
    <https://github.com/pyvista/vtk-data/tree/master/Data/ivan-nikolov>`_

    Parameters
    ----------
    load : bool, default: True
        Load the dataset after downloading it when ``True``.  Set this
        to ``False`` and only the filename will be returned.

    progress_bar : bool, default: False
        Display a progress_bar bar when downloading the file. Requires ``tqdm``.

    Returns
    -------
    pyvista.PolyData or str
        DataSet or filename depending on ``load``.

    Examples
    --------
    Download and plot the dataset.

    >>> from pyvista import examples
    >>> mesh = examples.download_sea_vase()
    >>> mesh.plot()

    Return the statistics of the dataset.

    >>> mesh  # doctest:+SKIP
    PolyData (0x7fe8b3862460)
      N Cells:      3548473
      N Points:     1810012
      X Bounds:     -1.666e+02, 1.465e+02
      Y Bounds:     -1.742e+02, 1.384e+02
      Z Bounds:     -1.500e+02, 2.992e+02
      N Arrays:     0

    """
    path, _ = _download_file('ivan-nikolov/seaVase.zip', progress_bar=progress_bar)
    filename = os.path.join(path, 'seaVase.vtp')
    if load:
        return pyvista.read(filename)
    return filename
