# Orthanc plugin for mammography
# Copyright (C) 2024 Edouard Chatzopoulos and Sebastien Jodogne,
# ICTEAM UCLouvain, Belgium
#
# This program is free software: you can redistribute it and/or
# modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


import download

import os
import numpy as np
import torch
import torch.nn as nn
import torchvision.transforms.v2 as transforms

from functools import partial
from torchvision.models.detection import RetinaNet
from torchvision.models.detection.anchor_utils import AnchorGenerator
from torchvision.models.detection.backbone_utils import _resnet_fpn_extractor
from torchvision.models.detection.retinanet import RetinaNetHead
from torchvision.models.resnet import resnet50, ResNet50_Weights
from torchvision.ops import FrozenBatchNorm2d
from torchvision.ops.feature_pyramid_network import LastLevelP6P7


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
MODELS_DIR = os.path.join(SCRIPT_DIR, 'models')

os.makedirs(MODELS_DIR, exist_ok = True)

download.get(os.path.join(MODELS_DIR, 'resnet50-11ad3fa6.pth'),
             'https://github.com/jodogne/orthanc-mammography/raw/master/models/resnet50-11ad3fa6.pth',
             102540417, '012571d812f34f8442473d8b827077b5')

download.get(os.path.join(MODELS_DIR, 'retina_res50_trained_08_03.pth'),
             'https://github.com/jodogne/orthanc-mammography/raw/master/models/retina_res50_trained_08_03.pth',
             145735292, '53aa159ea0b83234d767aacb43619748')


class ResizeBetter:
    def __init__(self, min_size=1750):
        self.min_size = min_size

    def __call__(self, sample):
        shape = sample[0].shape[-2:]
        return transforms.Resize((self.min_size,int(self.min_size*shape[1]/shape[0])),
                                 interpolation=transforms.InterpolationMode.BILINEAR,
                                 antialias=True)(sample)


def anchorgen():
    anchor_sizes = tuple((x, int(x * 2 ** (1.0 / 3)), int(x * 2 ** (2.0 / 3))) for x in [32, 64, 128, 256, 512])
    aspect_ratios = ((0.5, 1.0, 2.0),) * len(anchor_sizes)
    anchor_generator = AnchorGenerator(anchor_sizes, aspect_ratios)
    return anchor_generator


def load_model(config, pretrained_path, mean=0, std=1):
    if False:
        # Download backbone from Internet
        model_backbone = resnet50(norm_layer = FrozenBatchNorm2d,
                                  weights=ResNet50_Weights.DEFAULT)
    else:
        weights = torch.load(os.path.join(MODELS_DIR, 'resnet50-11ad3fa6.pth'), map_location=torch.device('cpu'))
        model_backbone = resnet50(norm_layer = FrozenBatchNorm2d)
        model_backbone.load_state_dict(weights)

    model_backbone.fc =  model_backbone.fc = nn.Sequential(
        nn.Linear(4*512 , config["num_classes"])
    )

    model_backbone = _resnet_fpn_extractor(model_backbone,
	                                       config["trainable_backbone_layers"],
	                                       returned_layers=[2, 3, 4],
	                                       extra_blocks=LastLevelP6P7(2048, 256))

    anchor_generator = anchorgen()

    head = RetinaNetHead(
        model_backbone.out_channels,
        anchor_generator.num_anchors_per_location()[0],
        config["num_classes"],
        norm_layer=partial(nn.GroupNorm, 32),
    )
    head.regression_head._loss_type = "giou"
    model = RetinaNet(model_backbone,
                      num_classes=config["num_classes"],
                      anchor_generator=anchor_generator,
                      head=head,
                      min_size=config["min_size"] ,
                      max_size=config["max_size"],
                      image_mean=[mean, mean, mean],
                      image_std=[std, std, std],
                      fg_iou_thresh=config["fg_iou_thresh"],
                      bg_iou_thresh=config["bg_iou_thresh"],
                      nms_thresh=config["nms_thresh"],
                      _skip_resize=True)

    if pretrained_path is not None:
        state_dict = torch.load(pretrained_path, map_location=torch.device('cpu'))
        model.load_state_dict(state_dict)
        print(f"Model loaded from checkpoint {pretrained_path}")

    for layer in model.modules():
        if isinstance(layer, nn.BatchNorm2d) or isinstance(layer, nn.BatchNorm1d):
            layer.eval()  # Set to evaluation mode
            layer.weight.requires_grad = False
            layer.bias.requires_grad = False

    model.eval()
    return model


def load_retina_net():
    config = {
        'num_classes' : 2,
        'min_size' : 2048,
        'max_size' : 2048,
        'trainable_backbone_layers' : 0,
        'fg_iou_thresh' : 0.5,
        'bg_iou_thresh' : 0.4,
        'nms_thresh' : 0.3,
    }

    return {
        'min_size' : config['min_size'],
        'eval' : load_model(config, os.path.join(MODELS_DIR, 'retina_res50_trained_08_03.pth')),
    }


def dicom_to_tensor(dicom, min_size):
    assert(len(dicom.pixel_array.shape) == 2)

    #Normalize the value scale to 0-255 (Useful for some processing steps)
    im_array = np.stack((dicom.pixel_array,)*3, axis=-1)
    im_max = np.max(im_array)
    im_min = np.min(im_array)
    image_tensor = torch.tensor(im_array.astype(np.float32).transpose(2, 0, 1))

    #Resize longest side to 2048 (with same ratio) and normalize
    image_tensor = ResizeBetter(min_size) (image_tensor)

    std = torch.std(image_tensor)
    mean = torch.mean(image_tensor)
    image_tensor = torch.sub(image_tensor, mean )
    image_tensor = torch.div(image_tensor, std)

    assert(len(image_tensor.shape) == 3)

    return image_tensor


def apply_model_to_dicom(model, dicom, rescale_boxes=True):
    image_tensor = dicom_to_tensor(dicom, model['min_size'])
    output = model['eval'] ([ image_tensor ])

    assert(len(output) == 1)
    output = output[0]

    if rescale_boxes:
        originalWidth = dicom.pixel_array.shape[1]
        originalHeight = dicom.pixel_array.shape[0]
        resizedWidth = image_tensor.shape[2]
        resizedHeight = image_tensor.shape[1]

        # TODO - The "int()" in ResizeBetter is anisotropic
        ratio = originalWidth / resizedWidth
        output['boxes'] *= ratio

    return output
