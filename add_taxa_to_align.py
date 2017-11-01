#! /usr/bin/env python
# add_taxa_to_align.py v1.0 created 2016-12-08

'''
add_taxa_to_align.py v1.3 2017-11-01
    add new taxa to an existing untrimmed alignment

    to add proteins from species1 and species2 to alignments prot1 and prot2:
add_taxa_to_align.py -a prot1.aln prot2.aln -t species1.fasta species2.fasta

    more generally as:
add_taxa_to_align.py -a *.aln -t new_transcriptomes/

    requires Bio Python library

    get hmmbuild and hmmscan (from hmmer package at http://hmmer.org/)

    for partitioned alignments, formats include:
  clustal, fasta, nexus, phylip, phylip-relaxed, stockholm

    partition file is comma-delimited text, as single or multiple lines
1:136,137:301,...

    no e-value threshold is set for hmmsearch, though results are filtered
    e-value cutoff can be determined automatically (default)
    or set manually with option -e
'''

import sys
import os
import argparse
import time
import subprocess
from collections import defaultdict
from glob import glob
from Bio import SeqIO
from Bio.Seq import Seq
from Bio import AlignIO

def get_partitions(partitionfile, errorlog):
	'''read comma-delimited partition information and return a list of tuples'''
	partitions = [] # list of tuples of intervals
	for line in open(partitionfile,'r'):
		line = line.strip()
		if line:
			blocks = line.split(",") # split "1:136,137:301,..." into ['1:136', '137:301',...]
			for block in blocks:
				alignindex = tuple( int(i) for i in block.split(":") ) # split '1:136' into ( 1,136 )
				partitions.append(alignindex)
	print >> errorlog, "# read {} partitions from {}".format(len(partitions), partitionfile), time.asctime()
	return partitions

def make_alignments(fullalignment, alignformat, partitions, partitiondir, errorlog):
	'''split large alignment into individual alignments, return the list of files'''
	splitalignments = [] # list of filenames
	alignedseqs = AlignIO.read(fullalignment, alignformat)
	for part in partitions:
		alignpartname = os.path.join(partitiondir, "{}_{}_{}_part.aln".format( os.path.splitext(os.path.basename(fullalignment))[0], part[0], part[1] ) )
		alignpart = alignedseqs[:, part[0]-1:part[1] ]
		with open(alignpartname, 'w') as ao:
			AlignIO.write(alignpart, ao, "fasta")
		splitalignments.append(alignpartname)
	print >> errorlog, "# split alignment by partitions", time.asctime()
	return splitalignments

def run_hmmbuild(HMMBUILD, alignmentfile, errorlog):
	'''generate HMM profile from multiple sequence alignment and return HMM filename'''
	# filename contains relative path, so should include partitions folder
	hmm_output = "{}.hmm".format(os.path.splitext(alignmentfile)[0] )
	hmmbuild_args = [HMMBUILD, hmm_output, alignmentfile]
	print >> errorlog, "{}\n{}".format(time.asctime(), " ".join(hmmbuild_args) )
	subprocess.call(hmmbuild_args, stdout=errorlog)
	print >> errorlog, "# hmmbuild completed", time.asctime()
	if os.path.isfile(hmm_output):
		return hmm_output
	else:
		raise OSError("Cannot find expected output file {}".format(hmm_output) )

def run_hmmsearch(HMMSEARCH, hmmprofile, fastafile, threadcount, hmmlog, hmmdir, errorlog):
	'''search fasta format proteins with HMM profile and return formatted-table filename'''
	hmmtbl_output = os.path.join(hmmdir, os.path.basename("{}_{}.tab".format(os.path.splitext(fastafile)[0], os.path.splitext(os.path.basename(hmmprofile))[0] ) ) )
	hmmsearch_args = [HMMSEARCH,"--cpu", str(threadcount), "--tblout", hmmtbl_output, hmmprofile, fastafile]
	print >> errorlog, "{}\n{}".format(time.asctime(), " ".join(hmmsearch_args) )
	if hmmlog:
		with open(hmmlog) as hmmstdout:
			subprocess.call(hmmsearch_args, stdout=hmmstdout)
	else:
		DEVNULL = open(os.devnull, 'w')
		subprocess.call(hmmsearch_args, stdout=DEVNULL)
	print >> errorlog, "# hmmsearch completed", time.asctime()
	if os.path.isfile(hmmtbl_output):
		return hmmtbl_output
	else:
		raise OSError("Cannot find expected output file {}".format(hmmtbl_output) )

def hmmtable_to_seqids(hmmtable, evaluecutoff, scorecutoff=0.5):
	'''parse hits from hmm tblout and return a list of kept protein IDs'''
#                                                               --- full sequence ---- --- best 1 domain ---- --- domain number estimation ----
# 0                  1          2                    3            4        5      6      7        8      9
# target name        accession  query name           accession    E-value  score  bias   E-value  score  bias   exp reg clu  ov env dom rep inc description of target
#10 11  12   13 14  15  16  17  18
#------------------- ---------- -------------------- ---------- --------- ------ ----- --------- ------ -----   --- --- --- --- --- --- --- --- ---------------------
	seqids_to_keep = []
	maxscore = 0
	for line in open(hmmtable, 'r').readlines():
		line = line.strip()
		if not line or line[0]=="#": # skip comment lines
			continue # also catch for empty line, which would cause IndexError
		lsplits = line.split(None,18)
		targetname = lsplits[0]
		evalue = float(lsplits[4])
		bitscore = float(lsplits[5])
		if bitscore > maxscore:
			maxscore = bitscore
		if evalue <= evaluecutoff and bitscore > maxscore*scorecutoff:
			seqids_to_keep.append(targetname)
	return seqids_to_keep

def get_evalue_from_hmm(HMMSEARCH, hmmprofile, alignment, threadcount, hmmevaluedir, errorlog, correction=1e5):
	'''get dynamic evalue from alignment and hmm'''
	fasta_unaligned = os.path.join( hmmevaluedir, "{}_no_gaps.fasta".format(os.path.splitext(os.path.basename(alignment))[0] ) )
	unalign_sequences(fasta_unaligned, alignment, notrim=True, calculatemedian=False, removeempty=True)
	hmmtbl_output = os.path.join( hmmevaluedir, os.path.basename( "{}_self_hmm.tab".format( os.path.splitext(alignment)[0] ) ) )
	hmmsearch_args = [HMMSEARCH,"--cpu", str(threadcount), "--tblout", hmmtbl_output, hmmprofile, fasta_unaligned]
	print >> errorlog, "{}\n{}".format(time.asctime(), " ".join(hmmsearch_args) )
	DEVNULL = open(os.devnull, 'w')
	subprocess.call(hmmsearch_args, stdout=DEVNULL)
	print >> errorlog, "# self-hmmsearch completed", time.asctime()
	if os.path.isfile(hmmtbl_output):
		maxevalue = 0.0
		for line in open(hmmtbl_output, 'r').readlines():
			line = line.strip()
			if not line or line[0]=="#": # skip comment lines
				continue # also catch for empty line, which would cause IndexError
			lsplits = line.split(None,18)
			targetname = lsplits[0]
			evalue = float(lsplits[4])
			if evalue > maxevalue:
				maxevalue = evalue
		if maxevalue==0.0: # if all evalues are 0.0, then set to 1e-300
			maxevalue = 1e-300
		else:
			maxevalue = maxevalue * correction # correct by set margin of error
		print >> errorlog, "# calculated e-value for {} as {:.3e}".format(alignment, maxevalue), time.asctime()
		return maxevalue
	else:
		raise OSError("Cannot find expected output file {}".format(hmmtbl_output) )

def unalign_sequences(unalignedtaxa, alignment, notrim, calculatemedian, removeempty):
	'''remove gaps from alignments, and possibly return median ungapped length'''
	sizelist = []
	with open(unalignedtaxa,'w') as notaln:
		for seqrec in SeqIO.parse(alignment,"fasta"):
			gappedseq = str(seqrec.seq)
			degappedseq = Seq(gappedseq.replace("-","").replace("X",""))
			seqrec.seq = degappedseq
			if calculatemedian:
				sizelist.append(len(degappedseq))
			if removeempty and len(degappedseq)==0:
				continue
			if notrim:
				notaln.write( seqrec.format("fasta") )
	if calculatemedian:
		median = sorted(sizelist)[len(sizelist)/2]
		return median
	else: # essentially void, just generates unaligned fasta file
		return None

def collect_sequences(unalignednewtaxa, alignment, hitlistolists, lengthcutoff, speciesnames, maxhits, dosupermatrix, notrim, verbose=False):
	'''write sequences from old alignment and new hits to file'''
	speciescounts = defaultdict(int) # key is species, value is number of written seqs per species
	median = unalign_sequences(unalignednewtaxa, alignment, notrim, calculatemedian=True, removeempty=False)
	with open(unalignednewtaxa,'a') as notaln:
		# hitlistolists is a list of lists, so that order of species is preserved
		for i,hitlist in enumerate(hitlistolists):
			writeout = 0
			for seqrec in hitlist: # sublist, each item is a SeqRecord object
				if writeout==maxhits: # if already have enough candidates
					break
				if len(seqrec.seq) >= median*lengthcutoff: # remove short sequences
					if dosupermatrix:
						seqrec.id = str(speciesnames[i])
						seqrec.description = ""
					notaln.write( seqrec.format("fasta") )
					writeout += 1
			if writeout==0: # all hits missed the cut or had no hits, give a dummy entry
				print >> notaln, ">{}".format(speciesnames[i])
				if verbose:
					print >> sys.stderr, "NO HITS FOR {} IN {}".format(speciesnames[i], alignment)
	# no return

def run_mafft(MAFFT, rawseqsfile, errorlog):
	'''generate multiple sequence alignment from fasta and return MSA filename'''
	aln_output = "{}.aln".format(os.path.splitext(rawseqsfile)[0] )
	aligner_args = [MAFFT, "--auto", "--quiet", rawseqsfile]
	print >> errorlog, "{}\n{}".format(time.asctime(), " ".join(aligner_args) )
	with open(aln_output, 'w') as msa:
		subprocess.call(aligner_args, stdout=msa)
	print >> errorlog, "# alignment of {} completed".format(aln_output), time.asctime()
	if os.path.isfile(aln_output):
		return aln_output
	else:
		raise OSError("Cannot find expected output file {}".format(aln_output) )

def run_mafft_addlong(MAFFT, oldalignment, rawseqsfile, errorlog):
	'''generate new MSA from fasta and old MSA and return MSA filename'''
	aln_output = "{}.aln".format(os.path.splitext(rawseqsfile)[0] )
	aligner_args = [MAFFT, "--quiet", "--keeplength", "--auto", "--addlong", rawseqsfile, oldalignment]
	print >> errorlog, "{}\n{}".format(time.asctime(), " ".join(aligner_args) )
	with open(aln_output, 'w') as msa:
		subprocess.call(aligner_args, stdout=msa)
	print >> errorlog, "# alignment of {} completed".format(aln_output), time.asctime()
	if os.path.isfile(aln_output):
		return aln_output
	else:
		raise OSError("Cannot find expected output file {}".format(aln_output) )

def run_tree(FASTTREEMP, alignfile, errorlog):
	'''generate tree from alignment'''
	tree_output = "{}.tree".format(os.path.splitext(alignfile)[0] )
	fasttree_args = [FASTTREEMP, "-quiet", alignfile]
	print >> errorlog, "{}\n{}".format(time.asctime(), " ".join(fasttree_args) )
	with open(tree_output, 'w') as tree:
		subprocess.call(fasttree_args, stdout=tree)
	if os.path.isfile(tree_output):
		return tree_output
	else:
		raise OSError("Cannot find expected output file {}".format(tree_output) )

def main(argv, wayout, errorlog):
	if not len(argv):
		argv.append('-h')
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
	parser.add_argument('-a','--alignments', nargs="*", help="alignment files or directory")
	parser.add_argument('-d','--directory', default="new_taxa", help="directory for new alignments [autonamed]")
	parser.add_argument('-e','--evalue', help="Evalue cutoff for hmmsearch [auto]")
	parser.add_argument('-E','--hmm-evalue-dir', default="hmm_vs_self", help="temporary directory for hmm self-search [./hmm_vs_self]")
	parser.add_argument('-f','--format', default="fasta", help="alignment format [fasta]")
	parser.add_argument('-i','--partition', help="optional partition file for splitting large alignments")
	parser.add_argument('-I','--partition-dir', default="partitions", help="temporary directory for partitioned alignments [./partitions]")
	parser.add_argument('-l','--length', type=float, default=0.5, help="minimum length cutoff compared to median [0.5]")
	parser.add_argument('-m','--max-hits', type=int, default=1, help="max number of allowed protein hits [1]")
	parser.add_argument('-p','--processors', type=int, default=1, help="number of processors [1]")
	parser.add_argument('-r','--no-trim', action="store_true", help="do not trim to original alignment in mafft")
	parser.add_argument('-s','--hmm-results', default=None, help="optional filename for hmmsearch output")
	parser.add_argument('-S','--hmm-dir', default="hmm_hits", help="temporary directory for hmm hits [./hmm_hits]")
	parser.add_argument('-t','--taxa', nargs="*", help="new taxa as fasta files of proteins (such as multiple translated transcriptomes) or directory")
	parser.add_argument('-T','--taxa-names', nargs="*", help="optional species names for supermatrix (can contain underscores, no spaces)")
	parser.add_argument('-U','--supermatrix', help="name for optional supermatrix output")
	parser.add_argument('--mafft', default="mafft", help="path to mafft binary [default is in PATH]")
	parser.add_argument('--hmmbin', default="", help="path to hmm binaries, should be a directory containing hmmbuild and hmmsearch [default is ./]")
	parser.add_argument('--fasttree', default="FastTreeMP", help="path to fasttree binary [default is in PATH]")
	args = parser.parse_args(argv)

	ALIGNER = os.path.expanduser(args.mafft)
	HMMBUILD = os.path.expanduser(os.path.join(args.hmmbin, "hmmbuild"))
	HMMSEARCH = os.path.expanduser(os.path.join(args.hmmbin, "hmmsearch"))
	FASTTREEMP = os.path.expanduser(args.fasttree)

	starttime = time.time()
	print >> errorlog, "# Script called as:\n{}".format( ' '.join(sys.argv) )

	### PROTEIN FILES FOR NEW TAXA
	if os.path.isdir(args.taxa[0]):
		print >> errorlog, "# Finding protein files from directory {}".format(args.taxa[0]), time.asctime()
		globstring = "{}*".format(args.taxa[0])
		newtaxafiles = glob(globstring)
	elif os.path.isfile(args.taxa[0]):
		newtaxafiles = args.taxa
	else:
		raise OSError("ERROR: Unknown new protein files, exiting")

	if args.taxa_names and len(args.taxa_names)!=len(args.taxa):
		raise ValueError("ERROR: number of taxa names does not match number of files, exiting")

	### SINGLE PARTITIONED ALIGNMENT TO BE EXTENDED
	if args.partition: # if partitioning, do this first
		if len(args.alignments) > 1:
			raise OSError("ERROR: Expecting 1 alignment, found {}, exiting".format( len(args.alignments) ) )
		elif not os.path.isfile(args.alignments[0]):
			raise OSError("ERROR: Cannot find {} alignment for partitions, exiting".format(args.alignments[0]) )
		else:
			partitions = get_partitions(args.partition, errorlog)
			if not os.path.isdir(args.partition_dir):
				if os.path.isfile(args.partition_dir):
					raise OSError("ERROR: Cannot create directory {}, exiting".format(args.partition_dir) )
				else:
					os.mkdir(args.partition_dir)
			alignfiles = make_alignments(args.alignments[0], args.format, partitions, args.partition_dir, errorlog)
	### ALIGNMENTS TO BE EXTENDED AS MULTIPLE FILES
	else: # otherwise treat alignments as normal, either directory or single file
		if os.path.isdir(args.alignments[0]):
			print >> errorlog, "# Reading alignments from directory {}".format(args.alignments[0]), time.asctime()
			globstring = "{}*".format(args.alignments[0])
			alignfiles = glob(globstring)
		elif os.path.isfile(args.alignments[0]):
			alignfiles = args.alignments
		else:
			raise OSError("ERROR: Unknown alignment files, exiting")

	### DIRECTORY FOR NEW OUTPUT
	timestring = time.strftime("%Y%m%d-%H%M%S")
	new_aln_dir = os.path.abspath( "{}_{}".format( timestring, args.directory ) )
	if not os.path.exists(new_aln_dir):
		os.mkdir(new_aln_dir)
		print >> errorlog, "# Creating directory {}".format(new_aln_dir), time.asctime()
	elif os.path.isdir(new_aln_dir):
		print >> errorlog, "# Using directory {}".format(new_aln_dir), time.asctime()

	### DIRECTORY FOR HMM RESULTS ###
	new_hmm_dir = os.path.abspath( "{}_{}".format( timestring, args.hmm_dir ) )
	if not os.path.isdir(new_hmm_dir):
		if os.path.isfile(new_hmm_dir):
			raise OSError("ERROR: Cannot create directory {}, exiting".format(new_hmm_dir) )
		else:
			print >> errorlog, "# Creating directory {}".format(new_hmm_dir), time.asctime()
			os.mkdir(new_hmm_dir)

	### DIRECTORY FOR HMM SELF SEARCH ###
	new_self_dir = os.path.abspath( "{}_{}".format( timestring, args.hmm_evalue_dir ) )
	if not os.path.isdir(new_self_dir):
		if os.path.isfile(new_self_dir):
			raise OSError("ERROR: Cannot create directory {}, exiting".format(new_self_dir) )
		else:
			print >> errorlog, "# Creating directory {}".format(new_self_dir), time.asctime()
			os.mkdir(new_self_dir)

	### MAIN LOOP
	supermatrix = None
	partitionlist = [] # empty list for new partition file
	runningsum = 0

	hmmprofilelist = [] # store hmms as list of files to run for each taxa
	aligntohmm = {} # key is alignment file, value is name of hmm profile
	evalueforhmmdict = {} # evalue is calculated once, stored as value where hmm name is key

	print >> errorlog, "# Building HMM profiles", time.asctime()
	for alignment in alignfiles:
		# make hmm profile from alignment, test against original set to determine evalue cutoff for new seqs
		hmmprofile = run_hmmbuild(HMMBUILD, alignment, errorlog)
		aligntohmm[alignment] = hmmprofile
		hmmprofilelist.append(hmmprofile)
		filtered_evalue = float(args.evalue) if args.evalue else get_evalue_from_hmm(HMMSEARCH, hmmprofile, alignment, args.processors, new_self_dir, errorlog)
		evalueforhmmdict[hmmprofile] = filtered_evalue

	# search each species sequentially, keep matches as SeqRecords in list of lists
	# to keep memory profile low, sec dict is remade for each species, then all HMMs are run
	seqrecs_to_add = defaultdict( list ) # key is hmm, value is list of lists of SeqRecords by species
	print >> errorlog, "# Beginning search for orthologs in new taxa", time.asctime()
	speciesnames = args.taxa_names if args.taxa_names else [os.path.basename(newspeciesfile) for f in newtaxafiles]
	for newspeciesfile in newtaxafiles:
		seqids_to_add = [] # build list of lists by species
		print >> errorlog, "# Reading proteins from {} into memory".format(newspeciesfile), time.asctime()
		seqdict = SeqIO.to_dict( SeqIO.parse(newspeciesfile, "fasta") )
		for hmmprof in hmmprofilelist:
			hmmtableout = run_hmmsearch(HMMSEARCH, hmmprof, newspeciesfile, args.processors, args.hmm_results, new_hmm_dir, errorlog)
			# append seqrecord to list for each hmm
			seqids_to_add = [ seqdict[hitseqid] for hitseqid in hmmtable_to_seqids(hmmtableout, evalueforhmmdict[hmmprof]) ] # is list of seqrecords
			# add this list for each hmm in the dict 'seqrecs_to_add'
			seqrecs_to_add[hmmprof].append(seqids_to_add)

	# then reiterate over each alignment, make the new fasta file, alignment, tree, and add to supermatrix
	for alignment in alignfiles:
		nt_unaligned = os.path.join(new_aln_dir, "{}.fasta".format(os.path.splitext(os.path.basename(alignment))[0] ) )
		collect_sequences(nt_unaligned, alignment, seqrecs_to_add[aligntohmm[alignment]], args.length, speciesnames, args.max_hits, args.supermatrix, args.no_trim)
		if args.no_trim: # use original method, which allows gaps from new sequences
			nt_aligned = run_mafft(ALIGNER, nt_unaligned, errorlog)
		else: # use --keeplength in mafft
			nt_aligned = run_mafft_addlong(ALIGNER, alignment, nt_unaligned, errorlog)

		# generate supermatrix from alignments
		newaligned = AlignIO.read(nt_aligned, "fasta")
		alignment_length = newaligned.get_alignment_length()
		partitionlist.append("{}:{}".format(runningsum+1, runningsum+alignment_length) )
		runningsum += alignment_length
		if supermatrix is None:
			supermatrix = newaligned
		else:
			supermatrix += newaligned
		nt_tree = run_tree(FASTTREEMP, nt_aligned, errorlog)

	### BUILD SUPERMATRIX
	if args.supermatrix:
		AlignIO.write(supermatrix, args.supermatrix, "fasta")
		print >> errorlog, "# Supermatrix written to {}".format(args.supermatrix), time.asctime()
		with open("{}.partition.txt".format(args.supermatrix),'w') as pf:
			print >> pf, ",".join(partitionlist)
	print >> errorlog, "# Process completed in {:.1f} minutes".format( (time.time()-starttime)/60 )

if __name__ == "__main__":
	main(sys.argv[1:], sys.stdout, sys.stderr)
