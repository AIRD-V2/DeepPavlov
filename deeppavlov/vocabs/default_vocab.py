from collections import Counter, defaultdict
import itertools

from deeppavlov.core.common.registry import register
from deeppavlov.core.models.trainable import Trainable
from deeppavlov.core.models.inferable import Inferable
from deeppavlov.core.common.attributes import check_path_exists


@register('default_vocab')
class DefaultVocabulary(Trainable, Inferable):

    def __init__(self, inputs, level='token',
                 model_dir='', model_file='vocab.txt',
                 special_tokens=('<UNK>',), default_token='<UNK>'): 
        self._model_dir = model_dir
        self._model_file = model_file
        self.special_tokens = special_tokens
        self.default_token = default_token
        self.preprocess_fn = self._build_preprocess_fn(inputs, level) 
        
        self.reset()
        if self.model_path_.exists():
            self.load()

    @staticmethod
    def _build_preprocess_fn(inputs, level):

        def iter_level(utter):
            if level == 'token':
                yield from utter.split(' ')
            elif level == 'char':
                yield from utter 
            else:
                raise ValueError("level argument is either equal to `token`"
                                 " or to `char`")

        def preprocess_fn(data):
            for f in inputs:
                if f == 'x':
                    yield from iter_level(data[0])
                elif f == 'y':
                    yield from iter_level(data[1])
                else:
                    yield from iter_level(data[2][f])

        return preprocess_fn

    def __getitem__(self, key):
        if isinstance(key, int):
#TODO: handle np.int != int
            return self._i2t[key]
        elif isinstance(key, str):
            return self._t2i[key]
        else:
            return NotImplemented("not implemented for type `{}`".format(type(key)))

    def __contains__(self, item):
        return item in self._t2i

    def __len__(self):
        return len(self.freqs)

    def keys(self):
        return (k for k, v in self.freqs.most_common())

    def values(self):
        return (v for k, v in self.freqs.most_common())

    def items(self):
        return self.freqs.most_common()

    def reset(self):
        def constant_factory(value):
            return itertools.repeat(value).__next__

	# default index is the position of default_token
        default_ind = self.special_tokens.index(self.default_token)
        self._t2i = defaultdict(constant_factory(default_ind))
        self._i2t = dict()
        self.freqs = Counter()

        for i, token in enumerate(self.special_tokens):
            self._t2i[token] = i
            self._i2t[i] = token
            self.freqs[token] += 0

    def train(self, data):
        self._train(
            tokens=filter(None, itertools.chain.from_iterable(
                map(self.preprocess_fn, data))),
            counts=None,
            update=True
        )
        self.save()

    def _train(self, tokens, counts=None, update=True):
        counts = counts or itertools.repeat(1)
        if not update:
            self.reset()

        index = len(self.freqs)
        for token, cnt in zip(tokens, counts):
            if token not in self._t2i:
                self._t2i[token] = index
                self._i2t[index] = token
                index += 1
            self.freqs[token] += cnt

    def infer(self, samples):
        return [self.__getitem__(s) for s in samples]

    def save(self):
        with open(self.model_path_, 'wt') as f:
            for token, cnt in self.freqs.most_common():
                f.write('{}\t{:d}\n'.format(token, cnt))

    @check_path_exists()
    def load(self):
        print("Loading vocabulary from `{}`".format(self.model_path_.absolute()))
        tokens, counts = [], []
        for ln in open(self.model_path_, 'r'):
            token, cnt = ln.split('\t', 1)
            tokens.append(token)
            counts.append(int(cnt))
        self._train(tokens=tokens, counts=counts, update=True)
