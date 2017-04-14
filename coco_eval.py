import sys
sys.path.append('tools/')
from python_utils import *
import pdb
import re
import numpy as np
import os
COCO_EVAL_PATH = os.environ["COCO_EVAL_PATH"] 
sys.path.insert(0,COCO_EVAL_PATH)
from pycocotools.coco import COCO
from pycocoevalcap.eval import COCOEvalCap
from pycocoevalcap.bleu.bleu import Bleu 
from pycocoevalcap.meteor.meteor import Meteor
from pycocoevalcap.rouge.rouge import Rouge
from pycocoevalcap.cider.cider import Cider
from pycocoevalcap.tokenizer.ptbtokenizer import PTBTokenizer

rm_word_dict = {'bus': ['bus', 'busses'],
                'bottle': ['bottle', 'bottles'],
                'couch': ['couch', 'couches', 'sofa', 'sofas'],
                'microwave': ['microwave', 'microwaves'],
                'pizza': ['pizza', 'pizzas'],
                'racket': ['racket', 'rackets', 'racquet', 'racquets'],
                'suitcase': ['luggage', 'luggages', 'suitcase', 'suitcases'],
                'zebra': ['zebra', 'zebras']}

class DCCScorer(COCOEvalCap):

  def get_dcc_scores(self):

    imgIds = self.params['image_id']
    # imgIds = self.coco.getImgIds()
    gts = {}
    res = {}
    for imgId in imgIds:
        gts[imgId] = self.coco.imgToAnns[imgId]
        res[imgId] = self.cocoRes.imgToAnns[imgId]
  
    tokenizer = PTBTokenizer()
    gts  = tokenizer.tokenize(gts)
    res = tokenizer.tokenize(res)    
    scorers = [
        (Bleu(4), ["Bleu_1", "Bleu_2", "Bleu_3", "Bleu_4"]),
        (Meteor(),"METEOR"),
        (Rouge(), "ROUGE_L"),
        (Cider(), "CIDEr")
    ]
    score_dict = {}
    for scorer, method in scorers:
      print 'computing %s score...'%(scorer.method())
      score, scores = scorer.compute_score(gts, res)
      if type(method) == list:
        for sc, scs, m in zip(score, scores, method):
          score_dict[m] = sc
          print "%s: %0.3f"%(m, sc)
      else:
        score_dict[method] = score
        print "%s: %0.3f"%(method, score)

    return score_dict

def split_sent(sent):
  sent = sent.lower()
  sent = re.sub('[^A-Za-z0-9\s]+','', sent)
  return sent.split()

def F1(generated_json, novel_ids, train_ids, word):
  set_rm_words = set(rm_word_dict[word])
  gen_dict = {}
  for c in generated_json:
    gen_dict[c['image_id']] = c['caption']

  #true positive are sentences that contain match words and should
  tp = sum([1 for c in novel_ids if len(set_rm_words.intersection(set(split_sent(gen_dict[c])))) > 0])
  #false positive are sentences that contain match words and should not
  fp = sum([1 for c in train_ids if len(set_rm_words.intersection(set(split_sent(gen_dict[c])))) > 0])
  #false positive are sentences that do not contain match words and should
  fn = sum([1 for c in novel_ids if len(set_rm_words.intersection(set(split_sent(gen_dict[c])))) == 0 ])

  #precision = tp/(tp+fp)
  if tp > 0:
    precision = float(tp)/(tp+fp)
    #recall = tp/(tp+fn)
    recall = float(tp)/(tp+fn)
    #f1 = 2* (precision*recall)/(precision+recall)
    return 2*(precision*recall)/(precision+recall)
  else:
    return 0.

def score_dcc(gt_template_novel, gt_template_train, 
              generation_result, words, dset='val_val'):

  score_dict_dcc = {}  
  generated_sentences = read_json(generation_result)
  f1_scores = 0
 
  for word in words:
    gt_file = gt_template_novel %(word, dset)

    gt_json_novel = read_json(gt_template_novel %(word, dset))
    gt_json_train = read_json(gt_template_train %(word, dset))
    gt_ids_novel = [c['image_id'] for c in gt_json_novel['annotations']]
    gt_ids_train = [c['image_id'] for c in gt_json_train['annotations']]
    gen = []
    for c in generated_sentences:
      if c['image_id'] in gt_ids_novel:
        gen.append(c)

    save_json(gen, 'tmp_gen.json')
    coco = COCO(gt_file)
    generation_coco = coco.loadRes('tmp_gen.json')
    dcc_evaluator = DCCScorer(coco, generation_coco)
    score_dict = dcc_evaluator.get_dcc_scores()
    os.remove('tmp_gen.json')

    for key in score_dict.keys():
      if key not in score_dict_dcc.keys():
        score_dict_dcc[key] = 0
      score_dict_dcc[key] += score_dict[key]

    f1_score = F1(generated_sentences, gt_ids_novel, gt_ids_train, word)
    print "F1 score for %s: %f" %(word, f1_score)
    f1_scores += f1_score

  print "########################################################################"
  for key in sorted(score_dict_dcc.keys()):
    score_dict_dcc[key] = score_dict_dcc[key]/len(words)
    print "Average %s: %0.3f" %(key, score_dict_dcc[key])
  print "Average F1 score: %f" %(f1_scores/len(words))

def score_generation(gt_filename=None, generation_result=None):

  coco = COCO(gt_filename)
  generation_coco = coco.loadRes(generation_result)
  coco_evaluator = COCOEvalCap(coco, generation_coco)
  coco_evaluator.evaluate()

def save_json_coco_format(caps, save_name):
  
  def get_coco_id(im_name):
    coco_id = int(im_name.split('/')[-1].split('_')[-1].split('.jpg')[0]) 
    return coco_id

  coco_format_caps = [{'caption': value, 'image_id': get_coco_id(key)} 
                       for value, key in zip(caps.values(), caps.keys())]

  save_json(coco_format_caps, save_name)


def save_json_other_format(caps, save_name):
  
  format_caps = [{'caption': value, 'image_id': key} 
                       for value, key in zip(caps.values(), caps.keys())]

  save_json(format_caps, save_name)

