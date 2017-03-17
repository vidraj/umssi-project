#!/usr/bin/env python3

### compare-conll.py
# Compare two CoNLL-X annotated files and report the ordered and unordered
#  accuracy of predictions vs. the gold-standard data.
#
# Usage:
# 	compare-conll.py GOLD PREDICTED



import sys
import re

gold_file = open(sys.argv[1], "rt")
pred_file = open(sys.argv[2], "rt")

# The total derivation count
total = 0
# The count of correctly connected, correctly oriented derivations.
correct = 0
# The count of incorrectly oriented derivations.
reordered = 0
# The count of incorrectly connected.
incorrect = 0

# Match a line in the CoNLL file, capture-group the address, word form and parent address.
conn_regex = re.compile('^(\d+)\t([^\t]+)(?:\t[^\t]+){4}\t(\d+)(?:\t[^\t]+){3}\n$')

derivations = {}
proposals = {}

for (gold, pred) in zip(gold_file, pred_file):
	if gold == "\n" and pred == "\n":
		# Start a new sentence when an empty line is found.
		# Evaluate the old sentence.
		assert len(derivations) == len(proposals)
		for address in proposals:
			proposed_parent = proposals[address]
			reordered_parent = derivations.get(pparent, None)
			
			if reordered_parent == address:
				# The derivation was merely reordered.
				reordered += 1
			else:
				# The derivation was actually wrong.
				incorrect += 1
		
		# Clear the tables
		derivations = {}
		proposals = {}
		continue
	
	total += 1
	
	# Parse the lines.
	gold_match = conn_regex.match(gold)
	pred_match = conn_regex.match(pred)
	(gaddress, gform, gparent) = gold_match.groups()
	(paddress, pform, pparent) = pred_match.groups()
	
	# Check that the lines belong to each other.
	assert gaddress == paddress, "Addresses on lines\n\tGold: '%s'\n\tPred: '%s'\nDon't match." % (gold, pred)
	assert gform == pform, "Forms on lines\n\tGold: '%s'\n\tPred: '%s'\nDon't match." % (gold, pred)
	
	
	if gparent == pparent:
		correct += 1
	else:
		# Save the derivation, it might be just misordered
		derivations[gaddress] = gparent
		proposals[paddress] = pparent


pred_file.close()
gold_file.close()

#print("Total: %d, correct: %d, reordered: %d, incorrect: %d." % (total, correct, reordered, incorrect))
#print("Ordered accuracy: %f, unordered accuracy: %f" % (correct / total, (correct + reordered) / total))
print("%f&%f" % (correct / total, (correct + reordered) / total))
