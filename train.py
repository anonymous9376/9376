import os
import numpy as np
import torch
import torch.utils.data as data
import argparse

from segmentation_loss import Dice_Loss
from segmentation import Unet3D as segnet
from autoencoder import Unet3D_encoder as encoder
from discriminator import discriminator
from ppmi import ppmi_pairs, onehot_tensor_to_segmap_numpy

from time import time
from metric import count_predictions, compute_metric, compute_dice_score

def train_epoch(models, optimizers, criterions, LAMBDA, train_set, batch_size,device):

	loader = data.DataLoader(train_set, batch_size = batch_size, num_workers = 16, pin_memory=True, shuffle = True)

	Encrypter = models['enc'].train()
	Segmentator = models['seg'].train()
	Discriminator = models['dis'].train()
	
	optimizer_es = optimizers['es']
	optimizer_d = optimizers['dis']
	
	segmentation_criterion = criterions['seg']
	discrimination_criterion = criterions['dis']
	
	run_seg_loss = 0
	run_adv_loss = 0
	dice_score = np.zeros(6)

	TP, FP, TN, FN = 0, 0, 0, 0
	
	start_time = time()
	for step, (x, x_ref, y, y_ref,d, d_p, d_n, im, im_ref) in enumerate(loader):
		'''train loop here'''
		x, x_ref, y, y_ref,d, d_p = x.to(device), x_ref.to(device), y.to(device), y_ref.to(device), d.to(device), d_p.to(device)
		
		'''Update segmentator and encoder'''
		optimizer_es.zero_grad()
		
		z = Encrypter(x)
		z_ref = Encrypter(x_ref)

		y_hat = Segmentator(z)
		y_hat_ref = Segmentator(z_ref)
		seg_loss_1 = segmentation_criterion(y_hat, y)
		seg_loss_2 = segmentation_criterion(y_hat_ref, y_ref)
		seg_loss = seg_loss_1 + seg_loss_2
		run_seg_loss += seg_loss.item()
		
		pred_1 = torch.round(y_hat).detach()
		dice_score += compute_dice_score(pred_1, y)
		pred_2 = torch.round(y_hat_ref).detach()
		dice_score += compute_dice_score(pred_2, y_ref)
		
		d_z_zref = Discriminator(z, z_ref)
		
		adv_loss = -discrimination_criterion(d_z_zref, d)
		
		run_adv_loss += adv_loss.item()
		
		loss = seg_loss + LAMBDA * adv_loss
		loss.backward()
		
		optimizer_es.step()
		
		'''Update discriminator'''
		optimizer_d.zero_grad()
		
		z = z.detach()
		z_ref = z_ref.detach()
		
		d_z_zref = Discriminator(z, z_ref)
		
		dis_loss = discrimination_criterion(d_z_zref, d)

		run_dis_loss += dis_loss.item()
		dis_loss.backward()
		optimizer_d.step()
		
		#print(step, seg_loss.item(), -adv_loss.item(),dis_loss.item())
		'''Count prediction'''
				
		_TP, _FP, _TN, _FN = count_predictions(d_z_zref, d)
		TP += _TP
		FP += _FP
		TN += _TN
		FN += _FN
		
	dur = (time() - start_time)	
	seg_loss = run_seg_loss / (step + 1)
	adv_loss = run_adv_loss / (step + 1)
	dis_acc = (TP + TN) / (TP + FP + TN + FN)
	dice_score = dice_score / (2 * (step+1))

	models = {'enc': Encrypter, 'seg': Segmentator, 'dis': Discriminator}
	optimizers = {'es': optimizer_es, 'dis': optimizer_d}
	
	print('|Train: ----------------------------')
	print('Seg_loss:{:.4f} | Adv_loss:{:.4f}'.format(seg_loss, -adv_loss))
	print('acc:{:.4f} | TP:{} FP:{} TN:{} FN:{} '.format(dis_acc, TP, FP, TN, FN))
	print('duration:{:.0f}'.format(dur))
	 
	return seg_loss, adv_loss,\
		   dis_acc, dice_score,\
		   models, optimizers

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('--device')
	parser.add_argument('')

if __name__ == '__main__':
	main()
