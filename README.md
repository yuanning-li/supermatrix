# supermatrix #
scripts to add new proteins to alignment using hmms

# check_supermatrix_alignments.py #
Quick diagnostic script to check matrix occupancy. Adjust format accordingly based on the alignment using the `-f` option. In most cases *phylip* format is probably *phylip-relaxed*

`check_supermatrix_alignments.py -a philippe2009_FullAlignment.phy -p philippe2009_partitions.txt -f phylip-relaxed`

Requires BioPython

# add_taxa_to_align #
Script to add new taxa to an existing protein supermatrix alignment. Proteins from new taxa are untrimmed, though a trimming step may be implemented. Input alignments could be in a number of formats, as a supermatrix with a separate partition file, or individual alignments as separate files. Multiple new taxa can be added with `-t`, as space-separate protein files (could be gene models or translated from transcriptomes). By default, only the single best hit is taken (chagned with `-m`), and is renamed to the corresponding species given in `-T`. Several folders with many intermediate files are generated, in case it is needed to re-examine later.

`add_taxa_to_align.py -a philippe2009_FullAlignment.phy -i philippe2009_partitions.txt -t ~/genomes/apis_mellifera/amel_OGSv3.2_pep.fa -e 1e-20 -T Apis_mellifera -f phylip-relaxed -U philippe2009_w_amel.aln`

Requires BioPython, [hmmsearch and hmmbuild](http://hmmer.org/), and [mafft](http://mafft.cbrc.jp/alignment/software/source.html), though could be modified to use any aligner.

# test alignments #
* Philippe et al 2009 dataset
* [Simion et al 2017](https://github.com/psimion/SuppData_Metazoa_2017), where partition file has been reduced to only the numbers and ? in the supermatrix are replaced with gaps
