import fairtest.bugreport.statistics.fairness_measures as fm
import pandas as pd
import numpy as np
from statsmodels.sandbox.stats.multicomp import multipletests

from multiprocessing import Process
from Queue import Queue


def compute_all_stats(experiments, approx, fdr):
        if fdr:
            fdr_alpha = 1-fdr
        else:
            fdr_alpha = None

        total_hypotheses = sum([num_hypotheses(exp)
                                for exp in experiments.values()])

        #
        # Adjusted Confidence Interval (Bonferroni)
        #
        # Compute effect sizes and p-values
        #
        adj_ci_level = None
        if fdr_alpha:
            adj_ci_level = 1-(1-fdr_alpha)/total_hypotheses

        all_stats = {sens: compute_stats(exp, approx, adj_ci_level)
                     for (sens, exp) in sorted(experiments.iteritems())}

        all_pvals = [max(stat[-1], 1e-180) for exp_stats in all_stats.values()
                     for stat in exp_stats['stats']]

        # correct p-values
        if fdr_alpha:
            _, pvals_corr, _, _ = multipletests(all_pvals,
                                                alpha=fdr_alpha,
                                                method='holm')

            idx = 0
            for (sens, exp) in experiments.iteritems():
                exp_stats = all_stats[sens]['stats']
                for i in range(len(exp_stats)):
                    old_stats = exp_stats[i]
                    all_stats[sens]['stats'][i] = \
                        np.append(old_stats[0:-1], pvals_corr[idx])
                    idx += 1

        for (sens, clusters) in experiments.iteritems():
            measure = clusters[0].clstr_measure
            # For regression, re-form the dataframes for each cluster
            if isinstance(measure.stats, pd.DataFrame):
                res = all_stats[sens]
                res = pd.DataFrame(res['stats'], index=res['index'],
                                   columns=res['cols'])
                all_stats[sens] = \
                    {'stats': np.array_split(res, len(res)/len(measure.stats))}

        all_stats = {sens: exp_stats['stats'] for (sens, exp_stats) in all_stats.iteritems()}

        #print all_stats

        return all_stats


def num_hypotheses(clusters):
    measure = clusters[0].clstr_measure
    #if measure.dataType == fm.Measure.DATATYPE_REG:
    #    return len(clusters)*measure.topK
    if isinstance(measure.stats, pd.DataFrame):
        return len(clusters)*len(measure.stats)
    else:
        return len(clusters)


def thread_compute(c, measure, approx, adj_ci_level, queue, idx):
    if measure.dataType == fm.Measure.DATATYPE_CORR:
        stats = c.clstr_measure.compute(c.stats, data=c.data['values'],
                                        approx=approx,
                                        adj_ci_level=adj_ci_level).stats
    else:
        stats = c.clstr_measure.compute(c.stats, approx=approx,
                                        adj_ci_level=adj_ci_level).stats

    queue.put(idx, stats)


def compute_stats(clusters, approx, adj_ci_level):

    measure = clusters[0].clstr_measure

    if measure.dataType == fm.Measure.DATATYPE_CORR:

        stats = map(lambda c: c.clstr_measure.
                    compute(c.stats, data=c.data['values'], approx=approx,
                            adj_ci_level=adj_ci_level).stats, clusters)

    else:
        stats = map(lambda c: c.clstr_measure.
                    compute(c.stats, approx=approx,
                            adj_ci_level=adj_ci_level).stats, clusters)
    '''

    queue = Queue()
    threads = []
    for idx, c in enumerate(clusters):
        t = Process(target=thread_compute, args=(c, measure, approx, adj_ci_level, queue, idx))
        threads.append(t)

    for idx, t in enumerate(threads):
        t.start()

    for idx, t in enumerate(threads):
        t.join()

    dict = {}

    for i in range(len(clusters)):
        (idx, stat) = queue.get()
        dict[idx] = stat
    stats = [dict[key] for key in sorted(dict)]
    print stats
    '''

    # For regression, we have multiple p-values per cluster
    # (one per topK coefficient)
    if isinstance(measure.stats, pd.DataFrame):
        stats = pd.concat(stats)
        index = stats.index
        cols = stats.columns
        stats = stats.values
        return {'stats': stats, 'index': index, 'cols': cols}

    return {'stats': stats}