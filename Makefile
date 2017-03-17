.PHONY: all clean dmvccm-all udp-all

# Naming convention: full == no sentence length restriction
#  number n = only sentences strictly shorter that n
#  -small = only 10000 randomly selected sentences
#  -tiny = only 1000 randomly selected sentences
CORP_FULLTAGS:=full 10 25 50
CORP_TAG1:=$(CORP_FULLTAGS:%=%-tag1) $(CORP_FULLTAGS:%=%-tag1-small) $(CORP_FULLTAGS:%=%-tag1-tiny) 10-tag1-small-nopunct 25-tag1-small-nopunct 10-tag1-tiny-nopunct 25-tag1-tiny-nopunct
CORP_VAR:=$(CORP_FULLTAGS) $(CORP_TAG1)
# corpora/corpus-full.conll corpora/corpus-10.conll corpora/corpus-25.conll corpora/corpus-50.conll
# and the same w/ short-tags
CORPORA:=$(CORP_VAR:%=corpora/corpus-%.conll)

# The directory to which to store Universal Linguistic Knowledge-formatted corpora
ULK_DIR:=./universal-knowledge/code

all: ulk-all-tag1.log dmvccm-all udp-all

# Run the Universal Linguistic Knowledge parsing on all datasets
# Don't use full tags, we don't have the appropriate map.
ulk-all-tag1.log: universal-knowledge ${CORPORA} launch-ulk-calculations.sh
	# The deps, poses and words files are created by the corpus preparation step, but the POS-mapping files are not.
	# Create them now.
	for v in $(CORP_TAG1); do cp universal-knowledge/code/map_czech "universal-knowledge/code/map_czech-$$v"; done # TODO not TAG1, but everything with short tags, including -tiny and -small
	
	# Compile the source.
	make -C universal-knowledge/code fast_dep.o
	
	# Launch the training phases. Be aware that this doesn't obey JOBS count, but launches a process for each CORP_VAR.
	echo Started at `date` > "$@"
	./launch-ulk-calculations.sh $(CORP_TAG1:%=czech-%) >> "$@" 2>&1
	echo Finished at `date` >> "$@"

# Run DMVCCM parsing on all datasets.
dmvccm-all: $(CORP_VAR:%=dmvccm-%.log)

# Run UDP parsing on all datasets.
udp-all: $(CORP_VAR:%=udp-%.log)

# Run DMVCCM for a single dataset.
dmvccm-%.log: corpora/corpus-%.conll train-dmvccm.py dmvccm
# 	./train-dmvccm.py "$<" corpora/dtest-raw.conll corpora/etest-raw.conll > "$@"
	# Test on training data, so that we don't give extra benefits to the other systems.
	./train-dmvccm.py "$<" > "$@" 2>&1

udp-%.log: corpora/corpus-%.conll udp/udpc/udpc
	./udp/udpc/udpc -i=1000br -attach -stop "$<" > "$@"


### Corpora preparation

# Copies the raw corpus, also creates the corpus for Universal Linguistic Knowledge.
corpora/corpus-full.conll: corpora/train-raw.conll filter-sentence-length.py universal-knowledge
	./filter-sentence-length.py -u "$(ULK_DIR)" "czech-full" "$<" > "$@"
corpora/corpus-full-tag1.conll: corpora/train-raw-tag1.conll filter-sentence-length.py universal-knowledge
	./filter-sentence-length.py -u "$(ULK_DIR)" "czech-full-tag1" "$<" > "$@"
corpora/corpus-%-small.conll: corpora/corpus-%.conll filter-sentence-length.py universal-knowledge
	./filter-sentence-length.py -u "$(ULK_DIR)" -rc 10000 "czech-$*-small" "$<" > "$@"
corpora/corpus-%-tiny.conll: corpora/corpus-%.conll filter-sentence-length.py universal-knowledge
	./filter-sentence-length.py -u "$(ULK_DIR)" -rc 1000 "czech-$*-tiny" "$<" > "$@"
# Create a corpus without len(sentences) >= %.
# Also create corpora for Universal Linguistic Knowledge.
corpora/corpus-%-tag1.conll: corpora/train-raw-tag1.conll filter-sentence-length.py universal-knowledge
	./filter-sentence-length.py -u "$(ULK_DIR)" -m "$*" "czech-$*-tag1" "$<" > "$@"
# FIXME hack: I have to list the possibilities explicitly here, because otherwise Make decides to match this against -tag1 in some (but not all?!) cases.
corpora/corpus-10.conll corpora/corpus-25.conll corpora/corpus-50.conll: corpora/corpus-%.conll: corpora/train-raw.conll filter-sentence-length.py universal-knowledge
	./filter-sentence-length.py -u "$(ULK_DIR)" -m "$*" "czech-$*" "$<" > "$@"

# Corpora without certain tags:
corpora/corpus-%-nopunct.conll: corpora/corpus-%.conll
	./filter-sentence-length.py -u "$(ULK_DIR)" -k Z "czech-$*-nopunct" "$<" > "$@"


# A target to obtain data from the CoNLL shared tasḱ instead of PDT-3.0 and trick the Makefile into believing that PDT is present.
conll: conll-2006-2007-cs.zip
	mkdir -p "$@"
	unzip -d "$@" "$<"
	mkdir -p pdt30
	touch pdt-train-files.txt pdt-dtest-files.txt pdt-etest-files.txt
	cp conll/2006/cs/train.conll corpora/train-raw.conll
	cp conll/2006/cs/test.conll corpora/dtest-raw.conll
	cp conll/2006/cs/test.conll corpora/etest-raw.conll

# Obtain a list of all analytical layer files.
# % is from {train dtest etest}.
pdt-%-files.txt: pdt30
	find pdt30/data/amw/$** -name '*.a.gz' > $@

# Create CoNLL files out of PDT-3.0 XML-based annotation.
# % is from {train dtest etest}.
corpora/%-raw.conll: pdt-%-files.txt
	treex -q --language=cs Read::PDT top_layer=a from="@$<" Write::CoNLLX to="$@"

# Cut the positional tags down to a single letter.
corpora/train-raw-tag1.conll: corpora/train-raw.conll
	bash -c 'paste <(cut -f-4 "$<") <(cut -f5 "$<" |cut -c1) <(cut -f6- "$<") |sed -e "s/^\t*$$//" > "$@"'

# Get and patch DMV+CCM
dmvccm: 0001-Load-corpora-from-CWD-instead-of-the-NLTK-repo.patch 0002-Port-treebank.py-to-new-NLTK-API.patch
	git clone 'https://github.com/davidswelt/dmvccm.git'
	git apply $^

# Unzip and patch Using Universal Linguistic Knowledge To Guide Grammar Induction
universal-knowledge: ulk.zip ulk-map_czech ulk-string.patch ulk-makefile.patch
	mkdir -p "$@"
	unzip -d "$@" "$<"
	
	# Patch the sources
	patch -p0 -i ulk-string.patch
	patch -p0 -i ulk-makefile.patch
	cp ulk-map_czech universal-knowledge/code/map_czech

ulk.zip:
	wget -O "$@" 'https://groups.csail.mit.edu/rbg/code/dependency/code.zip'

# Compile UDP
udp/udpc/udpc: udp
	make -C udp/udpc

udp: udp-12.04.tar.gz
	mkdir -p "$@"
	tar -C "$@" -xf "$<"

udp-12.04.tar.gz:
	wget -O "$@" 'https://ufal.mff.cuni.cz/~marecek/udp/udp-12.04.tar.gz'

clean:
	rm -rf conll
	rm -f corpora/corpus-*.conll
	
	rm -f ulk
# 	rm -rf ulk.zip universal-knowledge
# 	rm -rf universal-knowledge/code/run__[0-9]*
# 	rm -f universal-knowledge/code/deps_czech-* universal-knowledge/code/map_czech-* universal-knowledge/code/poses_czech-* universal-knowledge/code/words_czech-*
	rm -f universal-knowledge/code/fast_dep.o
	
	rm -rf udp
	
# 	rm -rf dmvccm




