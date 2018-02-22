import click

import cooler

from . import cli
from .. import expected



# might be relevant to us ...
# https://stackoverflow.com/questions/46577535/how-can-i-run-a-dask-distributed-local-cluster-from-the-command-line
# http://distributed.readthedocs.io/en/latest/setup.html#using-the-command-line


@cli.command()
@click.argument(
    "cool_path",
    metavar="COOL_PATH",
    type=str,
    nargs=1)
@click.option(
    '--nproc', '-n',
    help="Number of processes to split the work between."
         "[default: 1, i.e. no process pool]",
    default=1,
    type=int)
@click.option(
    "--chunksize", "-c",
    help="Control the number of pixels handled by each worker process at a time.",
    type=int,
    default=int(10e6),
    show_default=True)
@click.option(
    '--contact-type',
    help="compute expected for cis or trans region"
    "of a Hi-C map.",
    type=click.Choice(['cis', 'trans']),
    default='cis',
    show_default=True,
    )
@click.option(
    "--drop-diags",
    help="Number of diagonals to neglect for cis contact type",
    type=int,
    default=2,
    show_default=True)
# can we use feature switch
# for --cis/--trans instead (?):
# http://click.pocoo.org/options/#feature-switches
# http://click.pocoo.org/parameters/#parameter-names
# @click.option(
#     '--cis',
#     'contact_type',
#     help="compute expected for cis or trans region"
#     "of a Hi-C map.",
#     flag_value='cis',
#     required=True
#     )
# @click.option(
#     '--trans',
#     'contact_type',
#     help="compute expected for cis or trans region"
#     "of a Hi-C map.",
#     flag_value='trans',
#     required=True
#     )

def compute_expected(cool_path, nproc, chunksize, contact_type, drop_diags):
    """
    Calculate either expected Hi-C singal
    either for cis or for trans regions of
    chromosomal interaction map.
    
    COOL_PATH : The paths to a .cool file with a balanced Hi-C map.

    """

    if nproc > 1:
        import distributed
        cluster = distributed.LocalCluster(n_workers=nproc)
        client = distributed.Client(cluster)
    # use dask if more than 1 process requested:
    use_dask = True if nproc > 1 else False

    # load cooler file to process:
    c = cooler.Cooler(cool_path)

    # execute EITHER cis OR trans (not both):
    if contact_type == 'cis':
        # list of regions in a format (chrom,start,stop),
        # when start,stop ommited, process entire chrom:
        regions = [ (chrom,) for chrom in c.chromnames ]
        expected_result = expected.cis_expected(clr=c,
                                       regions=regions,
                                       field='balanced',
                                       chunksize=chunksize,
                                       use_dask=use_dask,
                                       ignore_diags=drop_diags)
    elif contact_type == 'trans':
        # process for all chromosomes:
        chromosomes = c.chromnames
        expected_result = expected.trans_expected(clr=c,
                                         chromosomes=chromosomes,
                                         chunksize=chunksize,
                                         use_dask=use_dask)
    # output to stdout,
    # just like in diamond_insulation:
    print(expected_result.to_csv(sep='\t', index=True, na_rep='nan'))

    # # DO WE HAVE TO SHUT DOWN SUCH CLUSTERS AT ALL ? ...
    # # ############
    # # # Shut down the whole distributed cluster
    # # # business, to avoid interference ...
    # # ############
    # if nproc > 1:
    #     # client.shutdown(timeout=1)
    #     # print(client.status)
    #     for w in cluster.workers:
    #         cluster.stop_worker(w)
    #     cluster.close()
