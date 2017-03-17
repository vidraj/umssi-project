#!/usr/bin/env python2

import sys
import copy
from dmvccm import dmv, ccm, dmvccm
from dep.conll import Czech



def format_word(w):
	# Format a single word-hashmap into CoNLL-X format with the unknown information represented by underscores.
	# The hash must contain the following records:
	# id, word, pos, parent
	# The format is:
	# ID	word	_	_	POS	_	parent	_	_	_
	# The IDs must be shifted by 1 first, because DMVCCM numbers the words from 0 and the technical root is -1
	return "%d\t%s\t_\t_\t%s\t%d\t_\t_\t_\n" % (w['id'] + 1, w['word'], w['pos'], w['parent'] + 1)


if len(sys.argv) == 2:
	train_file = sys.argv[1]
	heldout_file = train_file
	test_file = train_file
elif len(sys.argv) == 4:
	train_file = sys.argv[1]
	heldout_file = sys.argv[2]
	test_file = sys.argv[3]
else:
	sys.stderr.write("Error: Bad args.\nUsage:\n\ttrain-dmvccm.py TRAIN [HELDOUT TEST]\n\tWhen only one file is supplied, it is used in all three roles.\n")
	sys.exit(1)




#model_type = dmvccm.DMVCCM # FIXME Doesn't work, barfs after second iteration.
model_type = dmv.DMV
#model_type = ccm.CCM
# The maximum amount of iterations to train for. Training can be stopped earlier when accuracy decreases. We only test on the best model obtained.
train_iters = 32
# Run up to overtrain_limit iterations when the accuracy is already decreasing. This allows us to see how the accuracy progresses beyond the optimum.
overtrain_limit = 3

# Load the corpora.
corpus_train = Czech(files=[train_file])
if heldout_file == train_file:
	corpus_heldout = corpus_train
else:
	corpus_heldout = Czech(files=[heldout_file])
if test_file == train_file:
	corpus_test = corpus_train
else:
	corpus_test = Czech(files=[test_file])

#print("Training stats:")
#corpus_train.print_stats()
#print("Testing stats:")
#corpus_test.print_stats()


# Initialize the model.
model = model_type(treebank=corpus_heldout, training_corpus=corpus_train)

# The evaluation format is (words_in_test, directed_accuracy, undirected_accuracy)
best_evaluation = (0, -1.0, -1.0)
best_model = None

for iter in range(train_iters):
	model.train(1)
	# model.eval() # Not needed, evaluation is called automatically at the end of each .train() call
	# Since we request only one iteration at a time, this means it will be called after each iteration.
	# After .eval() is executed, .evaluation becomes accessible
	
	# Let's optimize against directed accuracy.
	if model.evaluation[1] >= best_evaluation[1]:
		# We have found a better model. Copy it and its statistics.
		best_evaluation = list(model.evaluation)
		best_model = copy.deepcopy(model)
	else:
		# We are overtraining.
		overtrain_limit -= 1
		if overtrain_limit <= 0:
			break

print("\n")
# Print some extra statistics on the model -- overproposed and underproposed derivations.
best_model.eval_stats()

print("\n\n")

# CCM
#model.parse(corpus_test.sents()[0])[0].treefy(corpus_test.sents()[0])


# Format the output into (incomplete) CoNLL-X
for tagged_sent in corpus_test.tagged_sents():
	# Represent each word in the sentence as a hashmap of the relevant information
	sentence = list(map(lambda pair: {'word': pair[0], 'pos': pair[1]}, tagged_sent))
	
	# Get the list of tags. These are needed for the prediction step.
	tags = list(map(lambda pair: pair[1], tagged_sent))
	# Get the predicted derivation links.
	# The format is a list of (word-id, parent) pairs. IDs are 0-based, ROOT is -1
	links_in_sentence = best_model.__class__.tree_to_depset(best_model.parse(tags)[0]).deps
	
	# Check that the model predicted the same count of links as there are words in the sentence
	assert(len(links_in_sentence) == len(sentence))
	
	# Fill the predicted derivation links into word-hashmaps
	for i in range(len(sentence)):
		assert(links_in_sentence[i][0] == i)
		sentence[i]['id'] = i
		sentence[i]['parent'] = links_in_sentence[i][1]
	
	# Print the sentence as CoNLL-X. Notice that there will be an additional newline at the end
	#  due to the print statement
	print(''.join(list(map(format_word, sentence))))
