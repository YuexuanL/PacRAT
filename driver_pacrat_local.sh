#!/bin/bash
#$ -S /bin/bash
#$ -l mfree=4G -pe serial 16 -l h_rt=0:48:0:0
#$ -cwd
#$ -N PacRAT

## There are two sections in this script; please be sure to comment/uncomment as appropriate for your situation

## ******* Section 2: Running locally with conda environment ******* #
## This is a sample for running PacRAT locally. We have here a skeleton of necessary steps you need to take in order to run PacRAT. Customize as needed.
## Please look at README file for directions on installing MUSCLE and NEEDLE. You must specify the location of the software.
## Use this section if you're choosing to run locally

# Validate that Anaconda/Miniconda are installed
SOURCECONDA=$(conda info --base)
if [ -z "$SOURCECONDA" ]
then
echo "Conda not available. Please install Anaconda or Miniconda https://docs.conda.io/en/latest/miniconda.html"
exit 1
fi

# Install and activate conda environment
ENVCHECK=$(conda env list | grep "pacrat_env")
source $SOURCECONDA/etc/profile.d/conda.sh
if [ -z "$ENVCHECK" ]
then
	echo "pacrat_env environment not installed! installing now..."
conda env create --file pacrat_env.yml
echo "pacrat_env environment installed"
else
echo "pacrat_env environment is installed!"
fi

conda activate pacrat_env
echo "Environment activated"

python pacrat.py -d ./output -o ARSA_barcode_variant_map_msa.txt \
	--highQual ../input/ARSA_NNK_barcodeInsertAssignment.tsv \
	--inputSeqs ../input/ARSA_NNK_barcodeInsertQuals.tsv \
	-c 1 -t 0.6 -s