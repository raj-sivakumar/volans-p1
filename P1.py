
# coding: utf-8

# In[1]:

import pyspark
from operator import add, itemgetter
import json
from string import punctuation
import math
from pyspark.conf import SparkConf
from string import punctuation


# # Calculating count of words in all docs combined

# In[2]:


sc = pyspark.SparkContext('local',appName="DocClassification")


# In[3]:


documents = sc.textFile("/home/vyom/UGA/DSP/Project1/X_train_vsmall.txt")


# In[4]:


labels = sc.textFile("/home/vyom/UGA/DSP/Project1/y_train_vsmall.txt")


# In[5]:


splt = documents.flatMap(lambda word: word.split())
splt = splt.map(lambda word: word.lower())

#Removing Punctuation
splt = splt.map(lambda word: word.replace("&quot",""))
cleanWords = splt.map(lambda word: word.strip(punctuation))
cleanWords = cleanWords.filter(lambda word:len(word)>0)

#Removing StopWord
stopWordFile = sc.textFile("/home/vyom/UGA/DSP/Project1/stopwords.txt")
stopWord = sc.broadcast(stopWordFile.collect())
lessWords = cleanWords.filter(lambda x: x not in stopWord.value)


# In[6]:


word = lessWords.map(lambda word : (word,1))


# In[7]:


CountinAllDocs = word.reduceByKey(add)


# In[8]:


CountinAllDocs = CountinAllDocs.sortBy(lambda x: x[1],False)


# In[9]:


numWords = sc.broadcast(CountinAllDocs.count())
numDocs = sc.broadcast(documents.count())


# # Calculating term frequency in each doc

# In[10]:


def stripWord(x):
    tempList =[]
    for word in x:
        word = word.replace("&quot","")
        word = word.strip(punctuation)
        if len(word)>0:
            tempList.append(word)
    return tempList


# In[11]:


def stripStopWord(x):
    tempList =[]
    for word in x:
        if word not in stopWord.value:
            tempList.append(word)
    return tempList


# In[12]:


def countWord(x):
    dictionary={}
    for word in x:
        if word not in dictionary:
            dictionary[word] = 1
        else:
            dictionary[word]+=1
    return dictionary


# In[13]:


bagOfWords = documents.map(lambda word: word.lower().split())
bagOfWords = bagOfWords.map(lambda x: stripWord(x))
bagOfWords = bagOfWords.map(lambda x: stripStopWord(x))
tf = bagOfWords.map(lambda x: countWord(x))


# # Calculating idf

# In[14]:


def uniques(x):
    tempList=[]
    for word in x:
        if word not in tempList:
            tempList.append(word);
    return tempList


# In[15]:


uniqueList = tf.map(lambda x: uniques(x))


# In[16]:


def initializeMap(x):
    tempList = []
    for word in x:
        tempList.append((word,1))
    return tempList


# In[17]:


occurences = sc.parallelize(uniqueList.map(lambda x: initializeMap(x)).reduce(add))
occurences = occurences.reduceByKey(add)


# In[18]:


idf = occurences.map(lambda x: (x[0],math.log(numDocs.value/x[1])))


# In[19]:


idf2 = sc.broadcast(idf.collectAsMap())


# # Calculating Tf-idf

# In[20]:


def getTfidf(x):
    tempDict={}
    idfDict=idf2.value
    for k,v in x.items():
        tempDict[k] = v*idfDict[k]
    return tempDict


# In[21]:


tfidf = tf.map(lambda x: getTfidf(x) )


# In[22]:


tfidfSorted = tfidf.map(lambda x: sorted(x.items(), key=itemgetter(1), reverse = True))


# # Implementing Naive Bayes

# ## Calculating word probability

# In[23]:


spltLabels = labels.map(lambda word: word.split(","))


# In[24]:


def removeUnnecessary(label):
    tempList=[]
    for word in label:
        if 'CAT' in word:
            tempList.append(word)
    return tempList


# In[25]:


requiredLabels = spltLabels.map(lambda label: removeUnnecessary(label))


# In[26]:


numberOfDocs = sc.broadcast(len(requiredLabels.reduce(add)))


# In[27]:


labelsToUse = sc.broadcast(requiredLabels.collect())


# In[28]:


def dictToList(x):
    tempList=[]
    for k, v in x.items():
        tempList.append((k,v))
    return tempList


# In[29]:


def getProbDoc(x,v):
    tempDict={}
    for label in labelsToUse.value[v]:
        tempDict[label] = x
    return tempDict


# In[30]:


ProbDocIndex = bagOfWords.zipWithIndex()


# In[31]:


ProbDoc = ProbDocIndex.map(lambda x: getProbDoc(x[0],x[1]) )


# In[32]:


ProbDocList= ProbDoc.map(lambda x : dictToList(x))


# In[33]:


ProbDocList = sc.parallelize(ProbDocList.reduce(add)).reduceByKey(add)


# In[34]:


labelWC = ProbDocList.map(lambda x: (x[0],len(x[1])))
labelWordCount =sc.broadcast(labelWC.collectAsMap())


# In[35]:


def countWord2(x):
    dictionary={}
    for word in x[1]:
        if word not in dictionary:
            dictionary[word] = 1
        else:
            dictionary[word]+=1
    return (x[0],dictionary)


# In[36]:


ProbDocListCount = ProbDocList.map(lambda x: countWord2(x))


# In[37]:


def getWordProbability(x):
    tempDict={}
    for k,v in x[1].items():
        tempDict[k]= v/labelWordCount.value[x[0]]
    return (x[0],tempDict)


# In[38]:


wordProbability = ProbDocListCount.map(lambda x: getWordProbability(x))


# In[39]:


def getLogProb(x):
    tempDict= {}
    for k,v in x[1].items():
        tempDict[k] = math.log(v)
    return (x[0],tempDict)


# In[40]:


logProbability = wordProbability.map(lambda x: getLogProb(x))


# ## Calculating Class Probability

# In[41]:


classList = sc.parallelize(requiredLabels.reduce(add))
classCount = classList.map(lambda x: (x,1)).reduceByKey(add)


# In[42]:


classProbability = classCount.map(lambda x: (x[0],x[1]/numberOfDocs.value))
classProb = sc.broadcast(classProbability.collectAsMap())

# #  Prediction

# In[45]:


testDocuments = sc.textFile("/home/vyom/UGA/DSP/Project1/X_test_vsmall.txt")
testLabels = sc.textFile("/home/vyom/UGA/DSP/Project1/y_test_vsmall.txt")


# In[46]:


bagOfWordsTest = testDocuments.map(lambda word: word.lower().split())
bagOfWordsTest = bagOfWordsTest.map(lambda x: stripWord(x))
bagOfWordsTest = bagOfWordsTest.map(lambda x: stripStopWord(x))


# In[47]:


testData = sc.broadcast(bagOfWordsTest.collect())


# In[48]:


def TestLogProbSum(x):
    tempDict={}
    for i in range(len(testData.value)):
        logSum=0;
        for word in testData.value[i]:
            if word in x[1]:
                logSum=logSum+x[1][word]
            else:
                logSum = logSum+ 1/labelWordCount.value[x[0]]
        tempDict[i]= logSum
    return (x[0],tempDict)


# In[49]:


logProbSum = logProbability.map(lambda x: TestLogProbSum(x))


# In[50]:


def getPrediction(x):
    tempDict={}
    for k,v in x[1].items():
        tempDict[k]= v*classProb.value[x[0]]
    return(x[0],tempDict)


# In[51]:


prediction = logProbSum.map(lambda x: getPrediction(x))


# In[52]:


for i in prediction.collect():
    print(i)
