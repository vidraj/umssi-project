#!/usr/bin/env python3

import sys
import re
import random
import argparse
from os.path import isdir, join
from nltk.corpus.reader.dependency import DependencyCorpusReader


parser = argparse.ArgumentParser(description="Read a CoNLL-X corpus, output filtered CoNLL-X and create files for Universal Linguistic Knowledge.")
parser.add_argument("corpus_suffix", metavar="CORPUS-SUFFIX", nargs='?', help="The suffix to add to Universal Knowledge files.")
parser.add_argument("file", metavar="FILE", help="CoNLL input file to process.")
parser.add_argument("-c", "--max-sentence-count", help="Only output this many sentences.", type=int)
parser.add_argument("-m", "--max-sentence-length", help="Only output sentences strictly shorter than this.", type=int)
parser.add_argument("-k", "--kill-tags", metavar="TAG-TO-KILL", action="append", default=[], help="Delete lexemes with this tag from the sentences. Can be specified multiple times.")
parser.add_argument("-r", "--random-order", action="store_true", help="Shuffle the data randomly.")
parser.add_argument("-s", "--sample", action="store_true", help="Draw a output-sized sample with replacement from the data.")
parser.add_argument("-u", "--universal-knowledge", help="A directory to put the Universal Knowledge files to. Default: None, files not generated.")
parser.add_argument("-v", "--verbose", action="store_true", help="Print extra messages.")
args = parser.parse_args()



if args.verbose:
	sys.stderr.write("Sentence length " + ("not restricted" if args.max_sentence_length is None else ("< %d" % args.max_sentence_length)) + "\n"
		  + "Sentence count " + ("not restricted" if args.max_sentence_count is None else ("restricted to the first %d" % args.max_sentence_count)) + "\n"
		  + "Shuffling " + ("enabled" if args.random_order else "disabled") + "\n"
		  + "Sampling " + ("enabled" if args.sample else "disabled") + "\n"
		  + "Killing " + (("tags %s" % ", ".join(args.kill_tags)) if len(args.kill_tags) > 0 else "no tags") + "\n"
		  + "Universal Knowledge files " + (("saved to %s" % args.universal_knowledge) if args.universal_knowledge is not None else "not generated") + "\n")
	
	#sys.stderr.write(str(dir(args)))


if args.universal_knowledge is not None:
	# Open the ULK-specific files.
	if isdir(args.universal_knowledge):
		words_f = open(join(args.universal_knowledge, "words_%s" % args.corpus_suffix), "wt")
		poses_f = open(join(args.universal_knowledge, "poses_%s" % args.corpus_suffix), "wt")
		deps_f = open(join(args.universal_knowledge, "deps_%s" % args.corpus_suffix), "wt")
	else:
		sys.stderr.write("Error: Universal Knowledge path '%s' is not a directory.\n" % args.universal_knowledge)
		sys.exit(1)


# The ULK files must not contain a newline at the end. Therefore, I write newlines
#  before the new line and I skip the newline at the very beginning of the file.
ulk_first_line = True

def print_ulk_format(tree):
	global ulk_first_line, words_f, poses_f, deps_f
	
	# The nodes are numbered 0 .. n, where 0 is the root of the sentence and 1 is the first word.
	# I have to renumber them to 0 .. n, where 0 is the first word and n is the root.
	# To do this, I move the root to n+1 and then shift everything by one to the left.
	root_id = len(tree.nodes)
	
	words_list = []
	poses_list = []
	deps_list = []
	
	# Go through all actual words (i.e. not the root) in the sentence and extract relevant info.
	for i in range(1, root_id):
		lexeme = tree.get_by_address(i)
		address = lexeme['address']
		form = lexeme['word']
		pos = lexeme['tag']
		parent = lexeme['head']
		
		assert(form is not None)
		assert(address == i)
		
		# Change the root address, if this lexeme depends on the root.
		if parent == 0:
			parent = root_id
		
		words_list.append(form)
		poses_list.append(pos)
		deps_list.append("%d-%d" % (parent - 1, address - 1)) # -1 is here due to the root reordering.
	
	# Put the root at the end.
	words_list.append('#')
	poses_list.append('#')
	
	# If we're NOT on the first line, end the previous line and start a new one.
	if ulk_first_line:
		ulk_first_line = False
	else:
		words_f.write("\n")
		poses_f.write("\n")
		deps_f.write("\n")
	
	words_f.write(' '.join(words_list))
	poses_f.write(' '.join(poses_list))
	deps_f.write(' '.join(deps_list))


def kill_node(sentence, address_to_delete):
	# Delete node with address "address" from the sentence and reattach all its children to its parent.
	
	# First, reparent all children of this node.
	# Don't use sentence.redirect_arcs() for this, it does the opposite reconnection!
	new_parent = sentence.nodes[address_to_delete]['head']
	for node in list(sentence.nodes.values()):
		if node['head'] == address_to_delete:
			node['head'] = new_parent
	
	# Then, delete this node.
	sentence.remove_by_address(address_to_delete)




# Open and read the corpus.
corpus = DependencyCorpusReader("./", [args.file])

sentences = corpus.parsed_sents()


## Apply transformations and filters to the data
# We have to kill tags before limiting length
# We have to shuffle and cut length before limiting count; otherwise we would end with improperly shuffled corpus
#  (sentences from beyond the limit would never appear) or with too few sentences, respectively.
#  Sampling limits length on its own naturally.


# First, kill tags.
if len(args.kill_tags) > 0:
	for sentence in sentences:
		for kill_tag in args.kill_tags:
			# Go over the sentence, matching tags.
			for address in list(sentence.nodes.keys()): # Make sure to fully construct the list ahead of time, otherwise Python complains that the dictionary changes while iterating.
				node = sentence.nodes[address]
				if node['tag'] == kill_tag:
					#sys.stderr.write("Killing node with address %d: %r\n" % (address, node))
					kill_node(sentence, address)
		
		
		# The addresses in the sentence may now be discontiguous. We have to fix that, otherwise DMV-CCM barfs and ULK gets harder to feed with properly formatted data.
		old_addrs = sorted(sentence.nodes.keys())
		
		# Create a mapping from old addresses to new ones.
		mapping = {}
		for new_address in range(len(sentence.nodes)):
			mapping[old_addrs[new_address]] = new_address
		
		# Use this mapping to remap all addresses in the tree.
		for node in list(sentence.nodes.values()):
			# Remap the address.
			old_addr = node['address']
			new_addr = mapping[old_addr]
			node['address'] = new_addr
			
			# Remap the dictionary key.
			del(sentence.nodes[old_addr])
			sentence.nodes[new_addr] = node
			
			# Remap the parent.
			old_parent = node['head']
			# ROOT has no parent, so check for that.
			if old_parent is not None:
				node['head'] = mapping[old_parent]
			
			# We don't care about what happens in the deps, we don't use them for anything.
			# Remap the reverse dependencies.
			#for afun in node['deps']:
				#old_parent_list = node['deps'][afun]
				#new_parent_list = list(map(lambda op: mapping[op], old_parent_list))
				#node['deps'][afun] = new_parent_list


# Then, limit sentence length.
if args.max_sentence_length is not None:
	# Get only sentences with less-than-or-equal max_sentence_length tokens. The ROOT token is included in this computation!
	# This means that I actually get sentences with strictly-less-than max_sentence_length tokens only.
	sentences = list(filter(lambda sentence: len(sentence.nodes) <= args.max_sentence_length, corpus.parsed_sents()))

# Then, randomize the order of sentence and extract the first N
if args.sample:
	# Sampling was requested, sample N items.
	count = args.max_sentence_count or len(sentences)
	sentences = random.choices(sentences, k=count)
else:
	# Sampling was not requested. Shuffle and cut if needed.
	if args.random_order:
		random.shuffle(sentences)

	if args.max_sentence_count is not None:
		sentences = sentences[:args.max_sentence_count]


for sentence in sentences:
	# If the sentence was killed completely, discard it.
	if len(sentence.nodes) <= 1:
		continue
	
	# Output the sentence in CoNLL-X.
	print(sentence.to_conll(10)) # 10 == long TSV format, corresponds to CONLL-X used in the 2006 CoNLL corpora.
	
	# Output the ULK files.
	if args.universal_knowledge is not None:
		# Write the ULK-specific format to the appropriate files.
		print_ulk_format(sentence)

if args.verbose:
	sys.stderr.write("Wrote %d sentences.\n" % len(sentences))

if args.universal_knowledge is not None:
	words_f.close()
	poses_f.close()
	deps_f.close()
