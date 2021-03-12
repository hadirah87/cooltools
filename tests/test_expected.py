import os.path as op
# import pandas as pd

import numpy as np
import pandas as pd
from numpy import testing

import bioframe
import cooler
from click.testing import CliRunner
import cooltools.expected
from cooltools.cli import cli

from itertools import combinations

# setup new testing infrasctructure for expected ...

# rudimentary expected functions for dense matrices:


def _diagsum_dense(matrix, ignore_diags=2, bad_bins=None):
    """
    function returning a diagsum list
    for a square symmetric and dense matrix
    it starts from the main diagonal and goes
    until the upper right element - the furthermost diagonal.
    """
    mat = matrix.copy().astype(float)
    if bad_bins is not None:
        mat[bad_bins, :] = np.nan
        mat[:, bad_bins] = np.nan

    # diagonal, starting from main one
    # all the way to the upper right element
    diags = range(len(mat))

    return [
        np.nanmean(mat.diagonal(i)) if (i >= ignore_diags) else np.nan for i in diags
    ]


def _diagsum_asymm_dense(matrix, bad_bin_rows=None, bad_bin_cols=None):
    """
    function returning a diagsum list
    for an arbitrary dense matrix, with no
    assumptions on symmetry.

    it starts from the bottom left element, goes
    through the "main" diagonal and to the upper
    right element - the frther most diagonal.
    """
    mat = matrix.copy().astype(float)
    if bad_bin_rows is not None:
        mat[bad_bin_rows, :] = np.nan
    elif bad_bin_cols is not None:
        mat[:, bad_bin_cols] = np.nan

    (mrows, mcols) = mat.shape

    # diagonals of an arbitrary rectangle matrix
    # negative diagonals are below the "main" one
    diags = range(-mrows + 1, mcols)

    return [np.nanmean(mat.diagonal(i)) for i in diags]
    # flatexp_tomat = lambda e,m_like: toeplitz(e[m_like.shape[0]-1::-1],e[m_like.shape[0]-1:])


def _blocksum_asymm_dense(matrix, bad_bin_rows=None, bad_bin_cols=None):
    """
    function returning a blocksum-based average
    for an arbitrary dense matrix, with no
    assumptions on symmetry.
    """
    mat = matrix.copy().astype(float)
    if bad_bin_rows is not None:
        mat[bad_bin_rows, :] = np.nan
    elif bad_bin_cols is not None:
        mat[:, bad_bin_cols] = np.nan

    return np.nanmean(mat)


# numpy.testing.assert_allclose(actual, desired, rtol=1e-07, atol=0, equal_nan=True, err_msg='', verbose=True)


# common parameters:
ignore_diags = 2
weight_name = "weight"
bad_bins = None
chunksize = 10_000  # keep it small to engage chunking
weight1 = weight_name + "1"
weight2 = weight_name + "2"
transforms = {"balanced": lambda p: p["count"] * p[weight1] * p[weight2]}


chromsizes = bioframe.fetch_chromsizes("mm9")
chromosomes = list(chromsizes.index)
supports = [(chrom, 0, chromsizes[chrom]) for chrom in chromosomes]

# test the most frequent use cases, balancing applied, no bad bins, etc.

common_regions = []
for i in range(4):
    chrom = chromosomes[i]
    halfway_chrom = int(chromsizes[chrom] / 2)
    reg1 = (chrom, 0, halfway_chrom)
    reg2 = (chrom, halfway_chrom, chromsizes[chrom])
    common_regions.append(reg1)
    common_regions.append(reg2)


def test_diagsum(request):
    # perform test:
    clr = cooler.Cooler(op.join(request.fspath.dirname, "data/CN.mm9.1000kb.cool"))
    res = cooltools.expected.diagsum(
        clr,
        regions=common_regions,
        transforms=transforms,
        weight_name=weight_name,
        bad_bins=bad_bins,
        ignore_diags=ignore_diags,
        chunksize=chunksize,
    )
    # calculate average:
    res["balanced.avg"] = res["balanced.sum"] / res["n_valid"]
    # check results for every "region"
    grouped = res.groupby("region")
    for name, group in grouped:
        matrix = clr.matrix(balance=weight_name).fetch(name)
        testing.assert_allclose(
            actual=group["balanced.avg"].values,
            desired=_diagsum_dense(matrix, ignore_diags=2),
            # rtol=1e-07,
            # atol=0,
            equal_nan=True,
        )


def test_diagsum_asymm(request):
    # perform test:
    clr = cooler.Cooler(op.join(request.fspath.dirname, "data/CN.mm9.1000kb.cool"))
    cis_pairwise_regions = [
        (r1, r2) for (r1, r2) in combinations(common_regions, 2) if (r1[0] == r2[0])
    ]
    regions1, regions2 = list(zip(*cis_pairwise_regions))
    res = cooltools.expected.diagsum_asymm(
        clr,
        regions1=regions1,
        regions2=regions2,
        transforms=transforms,
        weight_name=weight_name,
        bad_bins=bad_bins,
        chunksize=chunksize,
    )
    # calculate average:
    res["balanced.avg"] = res["balanced.sum"] / res["n_valid"]
    # check results for every block, defined as region1/2
    grouped = res.groupby(["region1", "region2"])
    for (name1, name2), group in grouped:
        matrix = clr.matrix(balance=weight_name).fetch(name1, name2)
        testing.assert_allclose(
            actual=group["balanced.avg"].values,
            desired=_diagsum_asymm_dense(matrix),
            # rtol=1e-07,
            # atol=0,
            equal_nan=True,
        )


def test_blocksum(request):
    # perform test:
    clr = cooler.Cooler(op.join(request.fspath.dirname, "data/CN.mm9.1000kb.cool"))
    all_pairwise_regions = combinations(common_regions, 2)
    regions1, regions2 = list(zip(*all_pairwise_regions))
    res = cooltools.expected.blocksum_asymm(
        clr,
        regions1=regions1,
        regions2=regions2,
        transforms=transforms,
        weight_name=weight_name,
        bad_bins=bad_bins,
        chunksize=chunksize,
    )
    # calculate average:
    res["balanced.avg"] = res["balanced.sum"] / res["n_valid"]
    # check results for every block , defined as region1/2
    # should be simplified as there is 1 number per block only
    grouped = res.groupby(["region1", "region2"])
    for (name1, name2), group in grouped:
        matrix = clr.matrix(balance=weight_name).fetch(name1, name2)
        testing.assert_allclose(
            actual=group["balanced.avg"].values,
            desired=_blocksum_asymm_dense(matrix),
            # rtol=1e-07,
            # atol=0,
            equal_nan=True,
        )


def test_expected_cli(request, tmpdir):
    # CLI compute-expected for chrom-wide cis-data
    in_cool = op.join(request.fspath.dirname, "data/CN.mm9.1000kb.cool")
    out_cis_expected = op.join(tmpdir, "cis.exp.tsv")
    runner = CliRunner()
    result = runner.invoke(
        cli, [
            'compute-expected',
            '--weight-name', weight_name,
            '-o', out_cis_expected,
            in_cool,
        ]
    )
    assert result.exit_code == 0
    clr = cooler.Cooler(in_cool)
    cis_expected = pd.read_table(out_cis_expected, sep="\t")
    grouped = cis_expected.groupby("region")
    # full chromosomes in this example:
    for chrom, group in grouped:
        matrix = clr.matrix(balance=weight_name).fetch(chrom)
        testing.assert_allclose(
            actual=group["balanced.avg"].values,
            desired=_diagsum_dense(matrix, ignore_diags=2),
            # rtol=1e-07,
            # atol=0,
            equal_nan=True,
        )


def test_expected_regions_cli(request, tmpdir):
    # CLI compute expected for cis-data with arbitrary regions
    # which may overlap. But it is symmetrical cis-case.
    in_cool = op.join(request.fspath.dirname, "data/CN.mm9.1000kb.cool")
    in_regions = op.join(request.fspath.dirname, "data/mm9.named_overlap_regions.bed")
    out_cis_expected = op.join(tmpdir, "cis.regions.exp.tsv")
    runner = CliRunner()
    result = runner.invoke(
        cli, [
            'compute-expected',
            '--weight-name', weight_name,
            '--regions', in_regions,
            '-o', out_cis_expected,
            in_cool,
        ]
    )
    assert result.exit_code == 0
    clr = cooler.Cooler(in_cool)
    cis_expected = pd.read_csv(out_cis_expected, sep="\t")
    grouped = cis_expected.groupby("region")
    # deal with named and overlapping regions here:
    regions_df = pd.read_csv(in_regions, sep="\t", header=None)
    regions_df = regions_df.set_index(3)
    for region_name, group in grouped:
        ucsc_region = regions_df.loc[region_name].to_list()
        matrix = clr.matrix(balance=weight_name).fetch(ucsc_region)
        testing.assert_allclose(
            actual=group["balanced.avg"].values,
            desired=_diagsum_dense(matrix, ignore_diags=2),
            # rtol=1e-07,
            # atol=0,
            equal_nan=True,
        )


def test_trans_expected_regions_cli(request, tmpdir):
    # CLI compute expected for cis-data with arbitrary regions
    # which may overlap. But it is symmetrical cis-case.
    in_cool = op.join(request.fspath.dirname, "data/CN.mm9.1000kb.cool")
    in_regions = op.join(request.fspath.dirname, "data/mm9.named_nonoverlap_regions.bed")
    out_trans_expected = op.join(tmpdir, "cis.regions.exp.tsv")
    runner = CliRunner()
    result = runner.invoke(
        cli, [
            'compute-expected',
            '--weight-name', weight_name,
            '--regions', in_regions,
            '--contact-type', 'trans',
            '-o', out_trans_expected,
            in_cool,
        ]
    )
    assert result.exit_code == 0
    clr = cooler.Cooler(in_cool)
    trans_expected = pd.read_csv(out_trans_expected, sep="\t")
    # grouped = trans_expected.groupby("region1","region2")
    trans_expected = trans_expected.set_index(["region1", "region2"])
    # deal with named and overlapping regions here:
    regions_df = pd.read_csv(in_regions, sep="\t", header=None)
    # prepare pairwise combinations of regions for trans-expected (blocksum):
    regions_pairwise = combinations(regions_df.itertuples(index=False), 2)
    regions1, regions2 = zip(*regions_pairwise)
    regions1 = pd.DataFrame(regions1)
    regions2 = pd.DataFrame(regions2)
    for i in range(len(trans_expected)):
        region1_name = regions1.iloc[i, 3]
        region2_name = regions2.iloc[i, 3]
        ucsc_region1 = regions1.iloc[i, :3].to_list()
        ucsc_region2 = regions2.iloc[i, :3].to_list()
        matrix = clr.matrix(balance=weight_name).fetch(ucsc_region1, ucsc_region2)
        testing.assert_allclose(
            actual=trans_expected.loc[(region1_name, region2_name), "balanced.avg"],
            desired=_blocksum_asymm_dense(matrix),
            # rtol=1e-07,
            # atol=0,
            equal_nan=True,
        )


def test_logbin_expected_cli(request, tmpdir):
    # test CLI logbin-expected for default chrom-wide output of compute-expected
    in_cool = op.join(request.fspath.dirname, "data/CN.mm9.1000kb.cool")
    out_cis_expected = op.join(tmpdir, "cis.exp.tsv")
    runner = CliRunner()
    result = runner.invoke(
        cli, [
            'compute-expected',
            '--weight-name', weight_name,
            '-o', out_cis_expected,
            in_cool,
        ]
    )
    assert result.exit_code == 0

    # consider adding logbin expected baswed on raw counts
    binsize = 1_000_000
    logbin_prefix = op.join(tmpdir, "logbin_prefix")
    runner = CliRunner()
    result = runner.invoke(
        cli, [
            'logbin-expected',
            '--resolution', binsize,
            out_cis_expected,
            logbin_prefix,
        ]
    )
    assert result.exit_code == 0
    # make sure logbin output is generated:
    assert op.isfile(f"{logbin_prefix}.log.tsv")
    assert op.isfile(f"{logbin_prefix}.der.tsv")
