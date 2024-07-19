# sematch
import nltk

from sematch.semantic.similarity import WordNetSimilarity
wns = WordNetSimilarity()

# Computing English word similarity using Li method
similarity = wns.word_similarity('cat', 'dog', 'li')# 0.449327301063
print("Similarity between 'dog' and 'cat' (Li method):", similarity)



