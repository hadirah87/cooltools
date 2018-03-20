####################
# collection of functions
# needed for dot-calling
####################

from scipy.linalg import toeplitz
from scipy.ndimage import convolve
from scipy.stats import poisson
from scipy.sparse import coo_matrix
import numpy as np
import pandas as pd
from sklearn.cluster import Birch



def multiple_test_BH(pvals,alpha=0.1):
    '''
    take an array of N p-values, sort then
    in ascending order p1<p2<p3<...<pN,
    and find a threshold p-value, pi
    for which pi < alpha*i/N, and pi+1 is
    already pi+1 >= alpha*(i+1)/N.
    Peaks corresponding to p-values
    p1<p2<...pi are considered significant.

    Parameters
    ----------
    pvals : array-like
        array of p-values to use for
        multiple hypothesis testing
    alpha : float
        rate of false discovery (FDR)

    
    Returns
    -------
    reject_ : numpy.ndarray
        array of type np.bool storing
        status of a pixel: significant (True)
        non-significant (False)
    pvals_threshold: tuple
        pval_max_reject_null, pval_min_accept_null

    Notes
    -----
    - Mostly follows the statsmodels implementation:
    http://www.statsmodels.org/dev/_modules/statsmodels/stats/multitest.html
    - Using alpha=0.02 it is possible to achieve
    called dots similar to pre-update status
    
    '''
    # 
    # prepare:
    pvals = np.asarray(pvals)
    n_obs = pvals.size
    # sort p-values ...
    sortind     = np.argsort(pvals)
    pvals_sort       = pvals[sortind]
    # the alpha*i/N_obs (empirical CDF):
    ecdffactor  = np.arange(1,n_obs+1)/float(n_obs)
    # for which observations to reject null-hypothesis ...
    reject_null = (pvals_sort <= alpha*ecdffactor)

    # let's extract border-line significant P-value:
    pval_max_reject_null = pvals_sort[ reject_null].max()
    pval_min_accept_null = pvals_sort[~reject_null].min()

    if reject_null.any():
        print("Some significant peaks have been detected!\n"
            "pval border is between {:.4f} and {:.4f}".format(
                                            pval_max_reject_null,
                                            pval_min_accept_null))
    # now we have to create ndarray reject_
    # that stores rej_null values in the order of
    # original pvals array ... 
    reject_ = np.empty_like(reject_null)
    reject_[sortind] = reject_null
    # return the reject_ status list and pval-range:
    return reject_, (pval_max_reject_null, pval_min_accept_null)




# consider using DBSCAN instead (picks cluster based on density estimation)
def clust_2D_pixels(pixels_df,threshold_cluster=2):
    '''
    Group significant pixels by proximity
    using Birch clustering.

    Parameters
    ----------
    pixels_df : pandas.DataFrame
        a DataFrame with pixel coordinates
        that must have at least 2 columns
        named 'bin1_id' and 'bin2_id',
        where first is pixels's row and the
        second is pixel's column index.
    threshold_cluster : int
        clustering radius for Birch clustering
        derived from ~40kb radius of clustering
        and bin size.

    
    Returns
    -------
    peak_tmp : pandas.DataFrame
        DataFrame with c_row,c_col,c_label,c_size - 
        columns. row/col are coordinates of centroids,
        label and sizes are unique pixel-cluster labels
        and their corresponding sizes.


    Notes
    -----
    TODO: figure out Birch clustering
    CFNodes etc, check if there might
    be some empty subclusters.
    
    '''
    # ###########
    # I suspect misup of row/col indices ...
    ##############
    # col (bin2) must precede row (bin1):
    pixels  = pixels_df[['bin1_id','bin2_id']].values
    pix_idx = pixels_df.index
    # clustering object prepare:
    brc = Birch(n_clusters=None,threshold=threshold_cluster)
    # cluster selected pixels ...
    brc.fit(pixels)
    brc.predict(pixels)
    # array of labels assigned to each pixel
    # after clustering: brc.labels_
    # array of (tuples?) with X,Y coordinates 
    # for centroids of corresponding clusters:
    # brc.subcluster_centers_
    uniq_labels, inverse_idx, uniq_counts = np.unique(
                                                brc.labels_,
                                                return_inverse=True,
                                                return_counts=True)
    # cluster sizes taken to match labels:
    clust_sizes = uniq_counts[inverse_idx]
    ####################
    # After discovering a bug ...
    # bug (or misunderstanding, rather):
    # uniq_labels is a subset of brc.subcluster_labels_
    # TODO: dive deeper into Birch ...
    ####################
    # repeat centroids coordinates
    # as many times as there are pixels
    # in each cluster:
    # IN OTHER WORDS (after bug fix):
    # take centroids corresponding to labels:
    centroids = np.take(brc.subcluster_centers_,
                        brc.labels_,
                        axis=0)

    # small message:
    print("Clustering is completed:\n"+
          "there are {} clusters detected\n".format(uniq_counts.size)+
          "mean size {:.6f}+/-{:.6f}\n".format(uniq_counts.mean(),
                                             uniq_counts.std())+
          "labels and centroids to be reported.")

    # let's create output DataFrame
    peak_tmp = pd.DataFrame(
                        centroids,
                        index=pix_idx,
                        columns=['cbin1_id','cbin2_id'])
    # add labels:
    peak_tmp['c_label'] = brc.labels_.astype(np.int)
    # add cluster sizes:
    peak_tmp['c_size'] = clust_sizes.astype(np.int)
    

    return peak_tmp



############################################################
# we need to make this work for slices
# of the intra-chromosomal Hi-C heatmaps
############################################################
def diagonal_matrix_tiling(start,
                           stop,
                           edge,
                           band):
    """
    generate a stream of tiling coordinates
    that guarantee to cover a diagonal area
    of the matrix of size 'band'.

    - cis-signal only...

    Each slice is characterized by the coordinate
    of the top-left corner and size.

    * * * * * * * * * * *  0-th slice
    *       *           *
    *       *           *
    *   * * * * *       *  i-th slice
    *   *   *   *       *
    * * * * *   *       *
    *   *       *       *
    *   * * * * *       *
    *                   *
    *              ...  *  ...
    *                   *
    *                   *
    * * * * * * * * * * *
    
    yield matrix tiles (raw, bal, exp, etc)
    these chunks are supposed to cover up
    a diagonal band of size 'band'.

    Specify a [start,stop) region of a matrix
    you want to tile diagonally.


    Parameters
    ----------
    start : int
        starting position of the matrix
        slice to be tiled (inclusive, bins,
        0-based).
    stop : int
        end position of the matrix
        slice to be tiled (exclusive, bins,
        0-based).
    edge : int
        small edge around each tile to be
        included in the yielded coordinates.
    band : int
        diagonal tiling is guaranteed to
        cover a diagonal are of width 'band'.

    Returns:
    --------
    yields pairs of indices for every chunk
    use those indices [cstart:cstop)
    to fetch chunks from the cooler-object:
     >>> clr.matrix()[cstart:cstop, cstart:cstop]
    """

    # # we could use cooler to extract bin_size
    # # and chromosome extent as [start,stop),
    # # but let's keep it agnostic ...
    # bin_size   = clr.info['bin-size']
    # start, stop = clr.extent(chrom)


    # matrix slice size [start,stop):
    size = stop - start
    # let's avoid delaing with bin_size explicitly ...
    # this function would be abstracted to bin-dimensions
    # ONLY !!!
    # # diagonal chunking to cover band-sized band around
    # # a diagonal:
    # band = int(band/bin_size)
    # # band = int(parse_humanized(band)/bin_size) if isinstance(band,str) \
    # #                                 else int(band/bin_size)
        
    # number of tiles ...
    tiles = size//band + bool(size%band)
    # actual number of tiles is tiles-1
    # since we're looping in range(1,tiles)
    
    ###################################################################
    # matrix parameters before chunking:
    print("matrix of size {}X{} to be splitted so that\n".format(size,size)+
     "  diagonal region of size {} would be completely\n".format(band)+
     "  covered by the tiling, additionally keeping\n"+
     "  a small 'edge' of size w={}, to allow for\n".format(edge)+
     "  meaningfull convolution around boundaries.\n"+
     "  Resulting number of tiles is {}".format(tiles-1)+
     "  Non-edge case size of each tile is {}X{}".format(2*(band+edge),2*(band+edge)))
    ###################################################################

    # instead of returning lists of
    # actual matrix-tiles, let's
    # simply yield pairs of [cstart,cstop)
    # coordinates for every chunk:
    
    # by doing range(1,tiles) we are making
    # sure we are processing the upper-left
    # chunk only once:
    for t in range(1,tiles):
        # l = max(0,M*t-M)
        # r = min(L,M*t+M)
        lw = max(0    , band*(t-1) - edge)
        rw = min(size , band*(t+1) + edge)
        # don't forget about the 'start' origin:
        yield lw+start, rw+start



############################################################
# we need to make this work for slices
# of the intra-chromosomal Hi-C heatmaps
############################################################
def square_matrix_tiling(start,
                         stop,
                         tile_size,
                         edge,
                         square=False):
    """
    generate a stream of tiling coordinates
    that guarantee to cover an entire matrix.

    - cis-signal only...

    Each slice is characterized by the coordinate
    of the top-left corner and size.

    * * * * * * * * * * * * *
    *       *       *       *
    *       *       *  ...  *
    *       *       *       *
    * * * * * * * * *       *
    *       *               *
    *       *    ...        *
    *       *               *
    * * * * *               *
    *                       *
    *                       *
    *                       *
    * * * * * * * * * * * * *

    Square parameter determines behavior
    of the tiling function, when the
    size of the matrix is not an exact
    multiple of the 'tile_size':

    square = False
    * * * * * * * * * * *
    *       *       *   *
    *       *       *   *
    *       *       *   *
    * * * * * * * * * * *
    *       *       *   *
    *       *       *   *
    *       *       *   *
    * * * * * * * * * * *
    *       *       *   *
    *       *       *   *
    * * * * * * * * * * *
    WARNING: be carefull with extracting
    expected in this case, as it is 
    not trivial at all !!!

    square = True
    * * * * * * * * * * *
    *       *   *   *   *
    *       *   *   *   *
    *       *   *   *   *
    * * * * * * * * * * *
    *       *   *   *   *
    *       *   *   *   *
    * * * * * * * * * * *
    * * * * * * * * * * *
    *       *   *   *   *
    *       *   *   *   *
    * * * * * * * * * * *
    
    yield matrix tiles (raw, bal, exp, etc)
    these chunks are supposed to cover up
    a diagonal band of size 'band'.


    Parameters
    ----------
    start : int
        starting position of the matrix
        slice to be tiled (inclusive, bins,
        0-based).
    stop : int
        end position of the matrix
        slice to be tiled (exclusive, bins,
        0-based).
    tile_size : int
        requested size of the tiles.
        Boundary tiles may or may not be
        of 'tile_size', see 'square'.
    edge : int
        small edge around each tile to be
        included in the yielded coordinates.
    band : int
        diagonal tiling is guaranteed to
        cover a diagonal are of width 'band'.


    Returns:
    --------
    yields pairs of indices for every chunk
    use those indices [cstart:cstop)
    to fetch chunks from the cooler-object:
     >>> clr.matrix()[cstart:cstop, cstart:cstop]
    """

    # # we could use cooler to extract bin_size
    # # and chromosome extent as [start,stop),
    # # but let's keep it agnostic ...
    # bin_size   = clr.info['bin-size']
    # start, stop = clr.extent(chrom)

    # matrix size:
    size = stop - start
        
    # number of tiles (just 1D) ...
    tiles = size//tile_size + bool(size%tile_size)
    
    ###################################################################
    # matrix parameters before chunking:
    print("matrix of size {}X{} to be splitted\n".format(size,size)+
     "  into square tiles of size {}.\n".format(tile_size)+
     "  A small 'edge' of size w={} is added, to allow for\n".format(edge)+
     "  meaningfull convolution around boundaries.\n"+
     "  Resulting number of tiles is {}".format(tiles*tiles))
    ###################################################################

    # instead of returning lists of
    # actual matrix-tiles, let's
    # simply yield pairs of [cstart,cstop)
    # coordinates for every chunk - 
    # seems like a wiser idea to me .

    for tx in range(tiles):
        for ty in range(tiles):
            # 
            lwx = max(0,    tile_size*tx - edge)
            rwx = min(size, tile_size*(tx+1) + edge)
            if square and (rwx >= size):
                lwx = size - tile_size - edge
            #         
            lwy = max(0,    tile_size*ty - edge)
            rwy = min(size, tile_size*(ty+1) + edge)
            if square and (rwy >= size):
                lwy = size - tile_size - edge
            #
            yield (lwx+start,rwx+start), (lwy+start,rwy+start)




################################################################
# internal function for "get_adjusted_expected_tile_some_nan"
################################################################
def _convolve_and_count_nans(O_bal,E_bal,E_raw,N_bal,kernel):
    """
    Dense versions of a bunch of matrices
    needed for convolution and calculation
    of number of NaNs in a vicinity of each
    pixel.
    And a kernel to be provided of course.
    """
    # a matrix filled with the kernel-weighted sums
    # based on a balanced observed matrix:
    KO = convolve(O_bal,
                  kernel,
                  mode='constant',
                  cval=0.0,
                  origin=0)
    # a matrix filled with the kernel-weighted sums
    # based on a balanced expected matrix:
    KE = convolve(E_bal,
                  kernel,
                  mode='constant',
                  cval=0.0,
                  origin=0)
    # get number of NaNs in a vicinity of every
    # pixel (kernel's nonzero footprint)
    # based on the NaN-matrix N_bal.
    # N_bal is shared NaNs between O_bal E_bal,
    # is it redundant ? 
    NN = convolve(N_bal.astype(np.int),
                  # we have to use kernel's
                  # nonzero footprint:
                  (kernel != 0).astype(np.int),
                  mode='constant',
                  # there are only NaNs 
                  # beyond the boundary:
                  cval=1,
                  origin=0)
    ######################################
    # using cval=0 for actual data and
    # cval=1 for NaNs matrix reduces 
    # "boundary issue" to the "number of
    # NaNs"-issue
    # ####################################

    # now finally, E_raw*(KO/KE), as the 
    # locally-adjusted expected with raw counts as values:
    Ek_raw = np.multiply(E_raw, np.divide(KO, KE))
    # return locally adjusted expected and number of NaNs
    # in the form of dense matrices:
    return Ek_raw, NN









########################################################################
# this should be a MAIN function to get locally adjusted expected
# Die Hauptfunktion
########################################################################
def get_adjusted_expected_tile_some_nans(origin,
                                         observed,
                                         expected,
                                         bal_weight,
                                         kernels,
                                         verbose=False):
    """
    'get_adjusted_expected_tile_some_nans', get locally adjusted
    expected for a collection of local-filters (kernels).

    Such locally adjusted expected, 'Ek' for a given kernel,
    can serve as a baseline for deciding whether a given
    pixel is enriched enough to call it a feature (dot-loop,
    flare, etc.) in a downstream analysis.

    For every pixel of interest [i,j], locally adjusted
    expected is a product of a global expected in that
    pixel E_bal[i,j] and an enrichment of local environ-
    ment of the pixel, described with a given kernel:
                              KERNEL[i,j](O_bal)
    Ek_bal[i,j] = E_bal[i,j]* ------------------
                              KERNEL[i,j](E_bal)
    where KERNEL[i,j](X) is a result of convolution
    between the kernel and a slice of matrix X centered
    around (i,j). See link below for details:
    https://en.wikipedia.org/wiki/Kernel_(image_processing)

    Returned values for observed and all expecteds
    are rescaled back to raw-counts, for the sake of
    downstream statistical analysis, which is using
    Poisson test to decide is a given pixel is enriched.
    (comparison between balanced values using Poisson-
    test is intractable):
                              KERNEL[i,j](O_bal)
    Ek_raw[i,j] = E_raw[i,j]* ------------------ ,
                              KERNEL[i,j](E_bal)
    where E_raw[i,j] is:
          1               1                 
    ------------- * ------------- * E_bal[i,j]
    bal_weight[i]   bal_weight[j]             
    

    Parameters
    ----------
    origin : (int,int) tuple
        tuple of interegers that specify the
        location of an observed matrix slice.
        Measured in bins, not in nucleotides.
    observed : numpy.ndarray
        square symmetrical dense-matrix
        that contains balanced observed O_bal
        !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        should we switch to RAW here ?
        it would be easy for the output ....
        !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    expected : numpy.ndarray
        square symmetrical dense-matrix
        that contains expected, calculated
        based on balanced observed: E_bal.
        !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        should we switch to its 1D representation here ?
        good for now, but expected might change later ...
        Tanay's expected, expected with modeled TAD's etc ...
        !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    bal_weight : numpy.ndarray or (numpy.ndarray, numpy.ndarray)
        1D vector used to turn raw observed
        into balanced observed for a slice of
        a matrix with the origin on the diagonal;
        and a tuple/list of a couple of 1D arrays
        in case it is a slice with an arbitrary 
        origin.
    kernels : dict of (str, numpy.ndarray)
        dictionary of kernels/masks to perform
        convolution of the heatmap. Kernels
        describe the local environment, and
        used to estimate baseline for finding
        enriched/prominent peaks.
        Peak must be enriched with respect to
        all local environments (all kernels),
        to be considered significant.
        Dictionay keys must contain names for
        each kernel.
        !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        Beware!: kernels are flipped and 
        only then multiplied to matrix by
        scipy.ndimage.convolve 
        !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    verbose: bool
        Set to True to print some progress
        messages to stdout.
    
    Returns
    -------
    peaks_df : pandas.DataFrame
        sparsified DataFrame that stores results of
        locally adjusted calculations for every kernel
        for a given slice of input matrix. Multiple
        instences of such 'peaks_df' can be concatena-
        ted and deduplicated for the downstream analysis.
        Reported columns: 
        bin1_id - bin1_id index (row), adjusted to origin
        bin2_id - bin bin2_id index, adjusted to origin
        la_exp - locally adjusted expected (for each kernel)
        la_nan - number of NaNs around (each kernel's footprint)
        exp.raw - global expected, rescaled to raw-counts
        obs.raw - observed values in raw-counts.
    """


    # extract origin coordinate of this tile:
    io, jo = origin
    # let's extract full matrices and ice_vector:
    O_raw = observed # raw observed, no need to copy, no modifications.
    E_bal = np.copy(expected)
    # 'bal_weight': ndarray or a couple of those ...
    if isinstance(bal_weight, np.ndarray):
        v_bal_i = bal_weight
        v_bal_j = bal_weight
    elif isinstance(bal_weight, (tuple,list)):
        v_bal_i,v_bal_j = bal_weight
    else:
        raise ValueError("'bal_weight' must be an numpy.ndarray"
                    "for slices of a matrix with diagonal-origin or"
                    "a tuple/list of a couple of numpy.ndarray-s"
                    "for a slice of matrix with an arbitrary origin.")
    # kernels must be a dict with kernel-names as keys
    # and kernel ndarrays as values.
    if not isinstance(kernels, dict):
        raise ValueError("'kernels' must be a dictionary"
                    "with name-keys and ndarrays-values.")

    # balanced observed, from raw-observed
    # by element-wise multiply:
    O_bal = np.multiply(O_raw, np.outer(v_bal_i,v_bal_j))
    # O_bal is separate from O_raw memory-wise.

    # raw E_bal: element-wise division of E_bal[i,j] and
    # v_bal[i]*v_bal[j]:
    E_raw = np.divide(E_bal, np.outer(v_bal_i,v_bal_j))

    # let's calculate a matrix of common NaNs
    # shared between observed and expected:
    # check if it's redundant ? (is NaNs from O_bal sufficient? )
    N_bal = np.logical_or(np.isnan(O_bal),
                          np.isnan(E_bal))
    # fill in common nan-s with zeroes, preventing
    # NaNs during convolution part of '_convolve_and_count_nans': 
    O_bal[N_bal] = 0.0
    E_bal[N_bal] = 0.0
    # think about usinf copyto and where functions later:
    # https://stackoverflow.com/questions/6431973/how-to-copy-data-from-a-numpy-array-to-another
    # 
    # 
    # we are going to accumulate all the results
    # into a DataFrame, keeping NaNs, and other
    # unfiltered results (even the lower triangle for now):
    i,j = np.indices(O_raw.shape)
    # pack it into DataFrame to accumulate results:
    peaks_df = pd.DataFrame({"bin1_id": i.flatten()+io,
                             "bin2_id": j.flatten()+jo})


    #
    for kernel_name, kernel in kernels.items():
        ###############################
        # kernel-specific calculations:
        ###############################
        # kernel paramters such as width etc
        # are taken into account implicitly ...
        ########################################
        Ek_raw, NN = _convolve_and_count_nans(O_bal,
                                            E_bal,
                                            E_raw,
                                            N_bal,
                                            kernel)
        if verbose:
            print("Convolution with kernel {} is complete.".format(kernel_name))
        #
        # accumulation into single DataFrame:
        # store locally adjusted expected for each kernel
        # and number of NaNs in the footprint of each kernel
        peaks_df["la_exp."+kernel_name+".value"] = Ek_raw.flatten()
        peaks_df["la_exp."+kernel_name+".nnans"] = NN.flatten()
        # do all the filter/logic/masking etc on the complete DataFrame ...
    #####################################
    # downstream stuff is supposed to be
    # aggregated over all kernels ...
    #####################################
    peaks_df["exp.raw"] = E_raw.flatten()
    peaks_df["obs.raw"] = O_raw.flatten()

    # TO BE REFACTORED/deprecated ...
    # compatibility with legacy API is completely BROKEN
    # post-processing allows us to restore it, see tests,
    # but we pay with the processing speed for it.
    mask_ndx = pd.Series(0, index=peaks_df.index, dtype=np.bool)
    for kernel_name, kernel in kernels.items():
        # accummulating with a vector full of 'False':
        mask_ndx_kernel = ~np.isfinite(peaks_df["la_exp."+kernel_name+".value"])
        mask_ndx = np.logical_or(mask_ndx_kernel,mask_ndx)

    # returning only pixels from upper triangle of a matrix
    # is likely here to stay:
    upper_band = (peaks_df["bin1_id"] < peaks_df["bin2_id"])
    # selecting pixels in relation to diagonal - too far, too
    # close etc, is now shifted to the outside of this function
    # a way to simplify code.

    # return good semi-sparsified DF:
    return peaks_df[~mask_ndx & upper_band].reset_index(drop=True)


