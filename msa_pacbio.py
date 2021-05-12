import os
import os.path
import numpy as np
from Bio import SeqIO
import glob
import sys
from Bio.Align.Applications import MuscleCommandline
#from StringIO import StringIO # for Python 2
from io import StringIO # for Python 3
from Bio import AlignIO
from Bio.Align import AlignInfo
from optparse import OptionParser
from datetime import datetime
from joblib import Parallel, delayed
import multiprocessing
import getpass


startTime = str(datetime.now())
print("Starting time: "+startTime)

# Option Parser
parser = OptionParser()
parser.add_option("-d","--directory", dest="workdir", help="Working directory",default=os.getcwd(),type="string")
parser.add_option("-o","--out", dest="out", help="Output file",default="Seq_barcodes_aligned.txt",type="string")
parser.add_option("--highQual", dest="highQualFile", help="File of barcode-seq association, seq from highest quality read",type="string")
parser.add_option("--inputSeqs", dest="inputSeqsFile", help="Raw barcode, sequence, quality input sequences",type="string")
# Additional options
parser.add_option("-c","--cutoff", dest="cutoff", help="Minimum number of ccs reads for analysis",default=2,type="int")
parser.add_option("-t","--threshold", dest="thresh", help="Minimum threshold to determine consensus sequence",default=0.7,type="float")
#parser.add_option("-a","--aligner", dest="aligner", help="Choose an aligner: muscle (default) or clustal",default="muscle",type="string",choices=["muscle", "clustal"])
parser.add_option("-v","--verbose", dest="verbose", help="Turn debug output on",default=False,action="store_true")
parser.add_option("-m","--muscle", dest="muscle", help="Compiled MUSCLE program",default="./muscle",type="string")
parser.add_option("-n","--needle", dest="needle", help="Compiled NEEDLE program",default="./needle",type="string")

(options, args) = parser.parse_args()

os.chdir(options.workdir)

#muscle_exe = "/net/gs/vol3/software/modules-sw/muscle/3.8.31/Linux/RHEL6/x86_64/bin/muscle"
#muscle_exe = "../../muscle/muscle"
#needle_exe = "../../emboss/EMBOSS-6.6.0/emboss/needle"
muscle_exe = options.muscle
needle_exe = options.needle

#create intermediates directories
os.system("mkdir -p intermediates & mkdir -p intermediates/fasta & mkdir -p intermediates/alignments & mkdir -p intermediates/fasta_2 & mkdir -p intermediates/realignments") 

outputfile = open(options.out, "w+")

print("Reading barcodes + reads file...")

# read original assignments into dictionary
hq_dict = {}
assignments = open(options.highQualFile, "r") # min_Q0_assignment.tsv
for line in assignments:
	paired_bcread = line.strip().split()
	hq_dict[paired_bcread[0]] = paired_bcread[1]
assignments.close()
print("Done reading HQ barcodes.")

# read all ccs reads into dict: BC: [seq1, seq2...]
# seq quality pairs stored as tuples
print("Reading all PB reads...")
read_dict = {}
reads = open(options.inputSeqsFile, "r") # seq_barcodes.txt
for line in reads: 
	paired_bcread = line.strip().split()
	#if paired_bcread[0] in ["AAAACCTTAT","AAAGACAAAA","AAAGATCCAG"]: debugging
	#	print(paired_bcread[1])
	if paired_bcread[0] in read_dict:
		read_dict[paired_bcread[0]].append(paired_bcread[1])
	else:
		read_dict[paired_bcread[0]] = [paired_bcread[1]]
reads.close()
totalBarcodes = len(hq_dict.keys())
print(str(totalBarcodes) + " barcodes found in hq file")
totalBarcodes2 = len(read_dict.keys())
print(str(totalBarcodes2) + " barcodes found in other file")

#consensus_dict = {}

# Giant for loop, now as a function
def loop_bcs(key):
	bc_entry = read_dict[key] #list of sequences
	#if len(bc_entry) == 0: print(key+" barcode not found in dictionary")
	#create fasta file for each barcode: 
	int_file_name = os.path.join("intermediates/fasta/" + key + ".fasta") 
	if not os.path.isfile(int_file_name):	
		intermediate_file = open(int_file_name, "w+")
		i = 0       
		for item in bc_entry: #add each read for a particular barcode in fasta format
			intermediate_file.write(">" + key + "_" + str(i) + "\n")
			intermediate_file.write(item+"\n")
			i = i+1
		intermediate_file.close()
	if options.verbose: print("made fasta file")

	# only align if there are at least CUTOFF ccs reads
	if len(bc_entry) >= options.cutoff:
		if len(bc_entry) == 1: #special case, don't need to align here
			outputfile.write(key+"\t"+bc_entry[0]+"\n")
			#consensus_dict[key] = bc_entry[0]
			
		else: 
			#align files together - first alignment
			aln_file_name = "intermediates/alignments/" + key + ".aln" # should this be os.path.join?
			#muscle system call here, write to output file
			muscle_cline = MuscleCommandline(muscle_exe, input=int_file_name, out=aln_file_name)
			stdout, stderr = muscle_cline(int_file_name)
			if options.verbose: print("passed cutoff, made first alignment")

			#get consensus: 
			consensus = ""
			if os.path.exists(aln_file_name): #probably should have an else here that throws an error, but it would be better to check that the muscle stderr is empty
				alignment = AlignIO.read(aln_file_name, 'fasta')
				summary_align = AlignInfo.SummaryInfo(alignment)
				consensus = summary_align.gap_consensus(threshold=options.thresh,  ambiguous='N')
				consensus = str(consensus)
				consensus = consensus.replace("-","") 
				if options.verbose: print("got consensus 1")	
		
			#if N's: realign (pairwise aligner w/in python) to highest qual, and find consensus from that
			if 'N' in consensus:
				#write 1st consensus and HQ read to new file
				int_file_name_2 = os.path.join("intermediates/fasta_2/" + key + ".fasta")
				fasta_2 = open(int_file_name_2,"w+")
				fasta_2.write(">"+key+"\n"+consensus)
				fasta_2.close()
				fasta_hq_name = os.path.join("intermediates/fasta_2/" + key + "_hq.fasta")
				fasta_hq = open(fasta_hq_name,"w+")
				fasta_hq.write(">"+key+"_hq\n"+hq_dict[key])
				fasta_hq.close()
				aln_file_name_2 = "intermediates/realignments/"+key+".aln"
				cmd = needle_exe + " " + int_file_name_2 + " " + fasta_hq_name + " -auto -gapopen 10 -gapextend 0.5 -outfile " + aln_file_name_2 + " -aformat fasta"
				os.system(cmd)
				#muscle_cline_2 = MuscleCommandline(muscle_exe, input=int_file_name_2, out=aln_file_name_2)
				#stdout, stderr = muscle_cline_2(int_file_name_2)

				#consensus of new alignment file (mostly same from previous script)
				alignment_2 = list(SeqIO.parse(aln_file_name_2,"fasta"))
				consensus_seq = str(alignment_2[0].seq)
				hq_seq = str(alignment_2[1].seq)
				finalSeq = ""
				lengthOfAlignment = len(consensus_seq)
				for i in range(lengthOfAlignment):
					if consensus_seq[i] == "N":
						finalSeq = finalSeq+hq_seq[i]
					else:
						finalSeq = finalSeq + consensus_seq[i]
				consensus = finalSeq
				consensus = consensus.replace("-","")		
				outputfile.write(key+"\t"+consensus+"\n")
				#consensus_dict[key] = consensus
				if options.verbose: print("realigned and got new consensus")
	
			#if no Ns: write consensus to output file
			else:
				outputfile.write(key+"\t"+consensus+"\n")
				#consensus_dict[key] = consensus
		
			if options.verbose: print("got consensus")
		outputfile.flush()


# Parallelization stuff
num_cores = multiprocessing.cpu_count()
print("Number of cores: " + str(num_cores))
results = Parallel(n_jobs=(num_cores),prefer="threads")(delayed(loop_bcs)(key) for key in hq_dict)

# print all consensus sequences to outfile
#totalCons = len(consensus_dict.keys())
#print("Sequences found for " + str(totalCons) + " barcodes")
#for bc, value in consensus_dict.items():
#	outputfile.write(bc+"\t"+value+"\n")
# close output file  
outputfile.close()

endTime = str(datetime.now())
print("Ending time: "+endTime)

#remove later?
recordTime = open("run_times.tsv","a+")
recordTime.write(str(getpass.getuser())+"\t"+startTime+"\t"+endTime+"\t"+str(num_cores)+"\n")
recordTime.close()
