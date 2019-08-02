import cv2
import numpy as np
from albumentations import Compose as Compose_albu
from albumentations import (
    PadIfNeeded,
    HorizontalFlip,
    GridDistortion,
    RandomBrightnessContrast,
    RandomGamma,
    Crop,
    LongestMaxSize,
    ShiftScaleRotate
)


def to_numpy(data):
    image, label = data['image'], data['label']
    data['image'] = np.array(image)
    if data['label'] is not None:
        data['label'] = np.array(label)
    return data


class Compose:
    def __init__(self, transforms):
        self.transforms = transforms
    
    def __call__(self, data):
        for t in self.transforms:
            data = t(data)
        return data


class MedicalTransform:
    def __init__(self, output_size, roi_error_range=0, type='train', use_roi=True):
        if isinstance(output_size, (tuple, list)):
            self.output_size = output_size  # (h, w)
        else:
            self.output_size = (output_size, output_size)
        
        self.roi_error_range = roi_error_range
        self.type = type
        self.use_roi = use_roi
    
    def __call__(self, data):
        data = to_numpy(data)
        img, label = data['image'], data['label']
        
        is_3d = True if img.shape == 4 and label.shape == 3 else False
        
        max_size = max(self.output_size[0], self.output_size[1])
        
        if self.type == 'train':
            task = [
                HorizontalFlip(p=0.5),
                RandomBrightnessContrast(p=0.5),
                RandomGamma(p=0.5),
                GridDistortion(border_mode=cv2.BORDER_CONSTANT, p=0.5),
                LongestMaxSize(max_size, p=1),
                PadIfNeeded(self.output_size[0], self.output_size[1], cv2.BORDER_CONSTANT, value=0, p=1),
                ShiftScaleRotate(shift_limit=0.2, scale_limit=0.5, rotate_limit=30, border_mode=cv2.BORDER_CONSTANT,
                                 value=0, p=0.5)
            ]
        else:
            task = [
                LongestMaxSize(max_size, p=1),
                PadIfNeeded(self.output_size[0], self.output_size[1], cv2.BORDER_CONSTANT, value=0, p=1),
            ]
        
        if self.use_roi:
            assert 'roi' in data.keys()
            roi = data['roi']
            crop = [Crop(roi['min_x'] - self.roi_error_range, roi['min_y'] - self.roi_error_range,
                         roi['max_x'] + self.roi_error_range, roi['max_y'] + self.roi_error_range, p=1), ]
            task = crop + task
        
        aug = Compose_albu(task)
        if not is_3d:
            aug_data = aug(image=img, mask=label)
            data['image'], data['label'] = aug_data['image'], aug_data['mask']
        
        else:
            keys = {}
            targets = {}
            for i in range(1, img.shape[2]):
                keys.update({f'image{i}': 'image'})
                keys.update({f'mask{i}': 'mask'})
                targets.update({f'image{i}': img[:, :, i]})
                targets.update({f'mask{i}': label[:, :, i]})
            aug.add_targets(keys)
            
            targets.update({'image': img[:, :, 0]})
            targets.update({'mask': label[:, :, 0]})
            
            aug_data = aug(**targets)
            imgs = [aug_data['image']]
            labels = [aug_data['mask']]
            
            for i in range(1, img.shape[2]):
                imgs.append(aug_data[f'image{i}'])
                labels.append(aug_data[f'mask{i}'])
            
            img = np.stack(imgs, axis=-1)
            label = np.stack(labels, axis=-1)
            data['image'] = img
            data['label'] = label
        
        return data
