############################################################################
# Copyright (c) 2015-2016 Saint Petersburg State University
# Copyright (c) 2011-2015 Saint Petersburg Academic University
# All Rights Reserved
# See file LICENSE for details.
############################################################################
from __future__ import with_statement
import os
from collections import defaultdict

from quast_libs import qconfig, qutils, reporting
from quast_libs.ca_utils.analyze_misassemblies import Misassembly
from quast_libs.ca_utils.misc import print_file, intergenomic_misassemblies_by_asm, ref_labels_by_chromosomes
import collections

class OrderedSet(collections.MutableSet):

    def __init__(self, iterable=None):
        self.end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add(self, key):
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key):
        if key in self.map:
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)

def print_results(contigs_fpath, log_out_f, used_snps_fpath, total_indels_info, result):
    gaps = result['gaps']
    neg_gaps = result['neg_gaps']
    misassembled_contigs = result['misassembled_contigs']
    region_misassemblies = result['region_misassemblies']
    log_out_f.write('Analysis is finished!\n')
    if qconfig.show_snps:
        log_out_f.write('Founded SNPs were written into ' + used_snps_fpath + '\n')
    log_out_f.write('\n')
    log_out_f.write('Results:\n')

    log_out_f.write('\tLocal Misassemblies: %d\n' % region_misassemblies.count(Misassembly.LOCAL))
    log_out_f.write('\tMisassemblies: %d\n' % (region_misassemblies.count(Misassembly.RELOCATION) +
                     region_misassemblies.count(Misassembly.INVERSION) + region_misassemblies.count(Misassembly.TRANSLOCATION) +
                     region_misassemblies.count(Misassembly.INTERSPECTRANSLOCATION)))
    log_out_f.write('\t\tRelocations: %d\n' % region_misassemblies.count(Misassembly.RELOCATION))
    log_out_f.write('\t\tTranslocations: %d\n' % region_misassemblies.count(Misassembly.TRANSLOCATION))
    if qconfig.is_combined_ref:
        log_out_f.write('\t\tInterspecies translocations: %d\n' % region_misassemblies.count(Misassembly.INTERSPECTRANSLOCATION))
    log_out_f.write('\t\tInversions: %d\n' % region_misassemblies.count(Misassembly.INVERSION))
    if qconfig.is_combined_ref:
        log_out_f.write('\tPotentially Misassembled Contigs (i/s translocations): %d\n' % region_misassemblies.count(Misassembly.POTENTIALLY_MIS_CONTIGS))
        log_out_f.write('\t\tPossible Misassemblies: %d\n' % region_misassemblies.count(Misassembly.POSSIBLE_MISASSEMBLIES))
    if qconfig.scaffolds and contigs_fpath not in qconfig.dict_of_broken_scaffolds:
        log_out_f.write('\tScaffold gap misassemblies: %d\n' % region_misassemblies.count(Misassembly.SCAFFOLD_GAP))
    if qconfig.bed:
        log_out_f.write('\tFake misassemblies matched with structural variations: %d\n' % result['misassemblies_matched_sv'])

    if qconfig.check_for_fragmented_ref:
        log_out_f.write('\tMisassemblies caused by fragmented reference: %d\n' % region_misassemblies.count(Misassembly.FRAGMENTED))
    log_out_f.write('\tMisassembled Contigs: %d\n' % len(misassembled_contigs))
    log_out_f.write('\tMisassembled Contig Bases: %d\n' % result['misassembled_bases'])
    log_out_f.write('\tMisassemblies Inter-Contig Overlap: %d\n' % result['misassembly_internal_overlap'])
    log_out_f.write('Uncovered Regions: %d (%d)\n' % (result['uncovered_regions'], result['uncovered_region_bases']))
    log_out_f.write('Unaligned Contigs: %d + %d part\n' % (result['unaligned'], result['partially_unaligned']))
    log_out_f.write('Half Unaligned Contigs with Misassemblies: %d\n' % result['half_unaligned_with_misassembly'])
    log_out_f.write('Unaligned Contig Bases: %d\n' % (result['fully_unaligned_bases'] + result['partially_unaligned_bases']))

    log_out_f.write('\n')
    log_out_f.write('Ambiguously Mapped Contigs: %d\n' % result['ambiguous_contigs'])
    log_out_f.write('Total Bases in Ambiguously Mapped Contigs: %d\n' % (result['ambiguous_contigs_len']))
    log_out_f.write('Extra Bases in Ambiguously Mapped Contigs: %d\n' % result['ambiguous_contigs_extra_bases'])
    if qconfig.ambiguity_usage == "all":
        log_out_f.write('Note that --allow-ambiguity option was set to "all" and each of these contigs was used several times.\n')
    elif qconfig.ambiguity_usage == "none":
        log_out_f.write('Note that --allow-ambiguity option was set to "none" and these contigs were skipped.\n')
    elif qconfig.ambiguity_usage == "one":
        log_out_f.write('Note that --allow-ambiguity option was set to "one" and only first alignment per each of these contigs was used.\n')

    if qconfig.show_snps:
        #log_out_f.write('Mismatches: %d\n' % result['SNPs'])
        #log_out_f.write('Single Nucleotide Indels: %d\n' % result['indels'])

        log_out_f.write('\n')
        log_out_f.write('\tCovered Bases: %d\n' % result['region_covered'])
        #log_out_f.write('\tAmbiguous Bases (e.g. N\'s): %d\n' % result['region_ambig'])
        log_out_f.write('\n')
        log_out_f.write('\tSNPs: %d\n' % total_indels_info.mismatches)
        log_out_f.write('\tInsertions: %d\n' % total_indels_info.insertions)
        log_out_f.write('\tDeletions: %d\n' % total_indels_info.deletions)
        #log_out_f.write('\tList of indels lengths:', indels_list)
        log_out_f.write('\n')
        log_out_f.write('\tPositive Gaps: %d\n' % len(gaps))
        internal = 0
        external = 0
        summ = 0
        for gap in gaps:
            if gap[1] == gap[2]:
                internal += 1
            else:
                external += 1
                summ += gap[0]
        log_out_f.write('\t\tInternal Gaps: %d\n' % internal)
        log_out_f.write('\t\tExternal Gaps: %d\n' % external)
        log_out_f.write('\t\tExternal Gap Total: %d\n' % summ)
        if external:
            avg = summ * 1.0 / external
        else:
            avg = 0.0
        log_out_f.write('\t\tExternal Gap Average: %.0f\n' % avg)

        log_out_f.write('\tNegative Gaps: %d\n' % len(neg_gaps))
        internal = 0
        external = 0
        summ = 0
        for gap in neg_gaps:
            if gap[1] == gap[2]:
                internal += 1
            else:
                external += 1
                summ += gap[0]
        log_out_f.write('\t\tInternal Overlaps: %d\n' % internal)
        log_out_f.write('\t\tExternal Overlaps: %d\n' % external)
        log_out_f.write('\t\tExternal Overlaps Total: %d\n' % summ)
        if external:
            avg = summ * 1.0 / external
        else:
            avg = 0.0
        log_out_f.write('\t\tExternal Overlaps Average: %.0f\n' % avg)

        redundant = list(set(result['redundant']))
        log_out_f.write('\tContigs with Redundant Alignments: %d (%d)\n' % (len(redundant), result['total_redundant']))
    return result


def save_result(result, report, fname, ref_fpath):
    region_misassemblies = result['region_misassemblies']
    misassemblies_by_ref = result['misassemblies_by_ref']
    region_struct_variations = result['region_struct_variations']
    misassemblies_matched_sv = result['misassemblies_matched_sv']
    misassembled_contigs = result['misassembled_contigs']
    misassembled_bases = result['misassembled_bases']
    misassembly_internal_overlap = result['misassembly_internal_overlap']
    unaligned = result['unaligned']
    partially_unaligned = result['partially_unaligned']
    partially_unaligned_bases = result['partially_unaligned_bases']
    fully_unaligned_bases = result['fully_unaligned_bases']
    ambiguous_contigs = result['ambiguous_contigs']
    ambiguous_contigs_extra_bases = result['ambiguous_contigs_extra_bases']
    SNPs = result['SNPs']
    indels_list = result['indels_list']
    total_aligned_bases = result['total_aligned_bases']
    half_unaligned_with_misassembly = result['half_unaligned_with_misassembly']

    report.add_field(reporting.Fields.MISLOCAL, region_misassemblies.count(Misassembly.LOCAL))
    report.add_field(reporting.Fields.MISASSEMBL, region_misassemblies.count(Misassembly.RELOCATION) +
                     region_misassemblies.count(Misassembly.INVERSION) + region_misassemblies.count(Misassembly.TRANSLOCATION) +
                     region_misassemblies.count(Misassembly.INTERSPECTRANSLOCATION))
    report.add_field(reporting.Fields.MISCONTIGS, len(misassembled_contigs))
    report.add_field(reporting.Fields.MISCONTIGSBASES, misassembled_bases)
    report.add_field(reporting.Fields.MISINTERNALOVERLAP, misassembly_internal_overlap)
    if qconfig.bed:
        report.add_field(reporting.Fields.STRUCT_VARIATIONS, misassemblies_matched_sv)
    report.add_field(reporting.Fields.UNALIGNED, '%d + %d part' % (unaligned, partially_unaligned))
    report.add_field(reporting.Fields.UNALIGNEDBASES, (fully_unaligned_bases + partially_unaligned_bases))
    report.add_field(reporting.Fields.AMBIGUOUS, ambiguous_contigs)
    report.add_field(reporting.Fields.AMBIGUOUSEXTRABASES, ambiguous_contigs_extra_bases)
    report.add_field(reporting.Fields.MISMATCHES, SNPs)
    # different types of indels:
    if indels_list is not None:
        report.add_field(reporting.Fields.INDELS, len(indels_list))
        report.add_field(reporting.Fields.INDELSBASES, sum(indels_list))
        report.add_field(reporting.Fields.MIS_SHORT_INDELS, len([i for i in indels_list if i <= qconfig.SHORT_INDEL_THRESHOLD]))
        report.add_field(reporting.Fields.MIS_LONG_INDELS, len([i for i in indels_list if i > qconfig.SHORT_INDEL_THRESHOLD]))

    if total_aligned_bases:
        report.add_field(reporting.Fields.SUBSERROR, "%.2f" % (float(SNPs) * 100000.0 / float(total_aligned_bases)))
        report.add_field(reporting.Fields.INDELSERROR, "%.2f" % (float(report.get_field(reporting.Fields.INDELS))
                                                                 * 100000.0 / float(total_aligned_bases)))

    # for misassemblies report:
    report.add_field(reporting.Fields.MIS_ALL_EXTENSIVE, region_misassemblies.count(Misassembly.RELOCATION) +
                     region_misassemblies.count(Misassembly.INVERSION) + region_misassemblies.count(Misassembly.TRANSLOCATION) +
                     region_misassemblies.count(Misassembly.INTERSPECTRANSLOCATION))
    report.add_field(reporting.Fields.MIS_RELOCATION, region_misassemblies.count(Misassembly.RELOCATION))
    report.add_field(reporting.Fields.MIS_TRANSLOCATION, region_misassemblies.count(Misassembly.TRANSLOCATION))
    report.add_field(reporting.Fields.MIS_INVERTION, region_misassemblies.count(Misassembly.INVERSION))
    report.add_field(reporting.Fields.MIS_EXTENSIVE_CONTIGS, len(misassembled_contigs))
    report.add_field(reporting.Fields.MIS_EXTENSIVE_BASES, misassembled_bases)
    report.add_field(reporting.Fields.MIS_LOCAL, region_misassemblies.count(Misassembly.LOCAL))
    if qconfig.is_combined_ref:
        report.add_field(reporting.Fields.MIS_ISTRANSLOCATIONS, region_misassemblies.count(Misassembly.INTERSPECTRANSLOCATION))
        report.add_field(reporting.Fields.CONTIGS_WITH_ISTRANSLOCATIONS, region_misassemblies.count(Misassembly.POTENTIALLY_MIS_CONTIGS))
        report.add_field(reporting.Fields.POSSIBLE_MISASSEMBLIES, region_misassemblies.count(Misassembly.POSSIBLE_MISASSEMBLIES))
        all_references = sorted(list(set([ref for ref in ref_labels_by_chromosomes.values()])))
        for ref_name in all_references:
            subreport = reporting.get(fname, ref_name=ref_name)
            ref_misassemblies = misassemblies_by_ref[ref_name]
            subreport.add_field(reporting.Fields.MIS_ALL_EXTENSIVE, ref_misassemblies.count(Misassembly.RELOCATION) +
                                ref_misassemblies.count(Misassembly.INVERSION) + ref_misassemblies.count(Misassembly.TRANSLOCATION) +
                                ref_misassemblies.count(Misassembly.INTERSPECTRANSLOCATION))
            subreport.add_field(reporting.Fields.MIS_RELOCATION, ref_misassemblies.count(Misassembly.RELOCATION))
            subreport.add_field(reporting.Fields.MIS_TRANSLOCATION, ref_misassemblies.count(Misassembly.TRANSLOCATION))
            subreport.add_field(reporting.Fields.MIS_INVERTION, ref_misassemblies.count(Misassembly.INVERSION))
            subreport.add_field(reporting.Fields.MIS_ISTRANSLOCATIONS, ref_misassemblies.count(Misassembly.INTERSPECTRANSLOCATION))
            subreport.add_field(reporting.Fields.MIS_LOCAL, ref_misassemblies.count(Misassembly.LOCAL))
            subreport.add_field(reporting.Fields.POSSIBLE_MISASSEMBLIES, ref_misassemblies.count(Misassembly.POSSIBLE_MISASSEMBLIES))
            subreport.add_field(reporting.Fields.CONTIGS_WITH_ISTRANSLOCATIONS, ref_misassemblies.count(Misassembly.POTENTIALLY_MIS_CONTIGS))
            if qconfig.scaffolds and fname not in qconfig.dict_of_broken_scaffolds:
                subreport.add_field(reporting.Fields.MIS_SCAFFOLDS_GAP, ref_misassemblies.count(Misassembly.SCAFFOLD_GAP))
            if qconfig.check_for_fragmented_ref:
                subreport.add_field(reporting.Fields.MIS_FRAGMENTED, ref_misassemblies.count(Misassembly.FRAGMENTED))
    elif intergenomic_misassemblies_by_asm:
        label = qutils.label_from_fpath(fname)
        ref_name = qutils.name_from_fpath(ref_fpath)
        ref_misassemblies = intergenomic_misassemblies_by_asm[label][ref_name]
        report.add_field(reporting.Fields.MIS_ISTRANSLOCATIONS, ref_misassemblies.count(Misassembly.INTERSPECTRANSLOCATION))
        report.add_field(reporting.Fields.POSSIBLE_MISASSEMBLIES, ref_misassemblies.count(Misassembly.POSSIBLE_MISASSEMBLIES))
        report.add_field(reporting.Fields.CONTIGS_WITH_ISTRANSLOCATIONS, ref_misassemblies.count(Misassembly.POTENTIALLY_MIS_CONTIGS))
    if qconfig.scaffolds and fname not in qconfig.dict_of_broken_scaffolds:
        report.add_field(reporting.Fields.MIS_SCAFFOLDS_GAP, region_misassemblies.count(Misassembly.SCAFFOLD_GAP))
    if qconfig.check_for_fragmented_ref:
        report.add_field(reporting.Fields.MIS_FRAGMENTED, region_misassemblies.count(Misassembly.FRAGMENTED))

    # for unaligned report:
    report.add_field(reporting.Fields.UNALIGNED_FULL_CNTGS, unaligned)
    report.add_field(reporting.Fields.UNALIGNED_FULL_LENGTH, fully_unaligned_bases)
    report.add_field(reporting.Fields.UNALIGNED_PART_CNTGS, partially_unaligned)
    report.add_field(reporting.Fields.UNALIGNED_PART_LENGTH, partially_unaligned_bases)
    report.add_field(reporting.Fields.UNALIGNED_MISASSEMBLED_CTGS, half_unaligned_with_misassembly)
    return report


def save_result_for_unaligned(result, report):
    unaligned_ctgs = report.get_field(reporting.Fields.CONTIGS)
    unaligned_length = report.get_field(reporting.Fields.TOTALLEN)
    report.add_field(reporting.Fields.UNALIGNED, '%d + %d part' % (unaligned_ctgs, 0))
    report.add_field(reporting.Fields.UNALIGNEDBASES, unaligned_length)

    report.add_field(reporting.Fields.UNALIGNED_FULL_CNTGS, unaligned_ctgs)
    report.add_field(reporting.Fields.UNALIGNED_FULL_LENGTH, unaligned_length)


def save_combined_ref_stats(results, contigs_fpaths, ref_labels_by_chromosomes, output_dir, logger):
    istranslocations_by_asm = [result['istranslocations_by_refs'] if result else None for result in results]
    misassemblies_by_asm = [result['misassemblies_by_ref'] if result else None for result in results]
    all_refs = list(OrderedSet([ref for ref in ref_labels_by_chromosomes.values()]))
    misassemblies_by_refs_rows = []
    row = {'metricName': 'References', 'values': all_refs}
    misassemblies_by_refs_rows.append(row)
    if not istranslocations_by_asm:
        return
    for i, fpath in enumerate(contigs_fpaths):
        label = qutils.label_from_fpath(fpath)
        row = {'metricName': label, 'values': []}
        misassemblies_by_refs_rows.append(row)
        istranslocations_by_ref = istranslocations_by_asm[i]
        intergenomic_misassemblies_by_asm[label] = defaultdict(list)
        for ref in all_refs:
            intergenomic_misassemblies_by_asm[label][ref] = misassemblies_by_asm[i][ref] if misassemblies_by_asm[i] else []
        if istranslocations_by_ref:
            assembly_name = qutils.name_from_fpath(fpath)
            all_rows = []
            row = {'metricName': 'References', 'values': [ref_num + 1 for ref_num in range(len(all_refs))]}
            all_rows.append(row)
            for ref in all_refs:
                row = {'metricName': ref, 'values': []}
                for second_ref in all_refs:
                    if ref == second_ref or second_ref not in istranslocations_by_ref:
                        row['values'].append(None)
                    else:
                        row['values'].append(istranslocations_by_ref[ref][second_ref])
                possible_misassemblies = 0
                misassemblies_by_ref = misassemblies_by_asm[i]
                if misassemblies_by_ref:
                    possible_misassemblies = misassemblies_by_ref[ref].count(Misassembly.POSSIBLE_MISASSEMBLIES)
                istranslocations = max(0, sum([r for r in row['values'] if r]))
                misassemblies_by_refs_rows[-1]['values'].append(istranslocations + possible_misassemblies)
                all_rows.append(row)
            misassembly_by_ref_fpath = os.path.join(output_dir, 'interspecies_translocations_by_refs_%s.info' % assembly_name)
            with open(misassembly_by_ref_fpath, 'w') as misassembly_by_ref_file:
                misassembly_by_ref_file.write('Number of interspecies translocations by references: \n')
            print_file(all_rows, misassembly_by_ref_fpath, append_to_existing_file=True)

            with open(misassembly_by_ref_fpath, 'a') as misassembly_by_ref_file:
                misassembly_by_ref_file.write('References:\n')
                for ref_num, ref in enumerate(all_refs):
                    misassembly_by_ref_file.write(str(ref_num + 1) + ' - ' + ref + '\n')
            logger.info('  Information about interspecies translocations by references for %s is saved to %s' %
                        (assembly_name, misassembly_by_ref_fpath))
    misassemblies = []
    if qconfig.draw_plots:
        from quast_libs import plotter

        aligned_contigs_labels = []
        for row in misassemblies_by_refs_rows[1:]:
            if row['values']:
                aligned_contigs_labels.append(row['metricName'])
            else:
                misassemblies_by_refs_rows.remove(row)
        for i in range(len(all_refs)):
            cur_results = []
            for row in misassemblies_by_refs_rows[1:]:
                if row['values']:
                    cur_results.append(row['values'][i])
            misassemblies.append(cur_results)
        is_translocations_plot_fpath = os.path.join(output_dir, 'intergenomic_misassemblies.' + qconfig.plot_extension)
        plotter.draw_meta_summary_plot('', output_dir, aligned_contigs_labels, all_refs, misassemblies_by_refs_rows,
                                       misassemblies,
                                       is_translocations_plot_fpath, title='# intergenomic misassemblies', reverse=False,
                                       yaxis_title=None, print_all_refs=True)
