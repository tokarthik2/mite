from dataclasses import InitVar, dataclass, field
from typing import Optional

from mite.scenario import StopScenario


@dataclass
class _VolumeModel:
    duration: int

    def _volume(self, start, end):
        raise NotImplementedError

    def __call__(self, start, end):
        if start > self.duration:
            raise StopScenario
        return self._volume(start, end)

    def __add__(self, other):
        if not isinstance(other, _VolumeModel):
            raise ValueError(f"Cannot add a {type(other)} to a volume model")
        return Compound(
            _left=self,
            _right=other,
            # duration will be overwritten in the init fn
            duration=0,
        )


@dataclass
class Nothing(_VolumeModel):
    def _volume(self, start, end):
        return 0


@dataclass
class Constant(_VolumeModel):
    tps: int

    def _volume(self, start, end):
        return self.tps


@dataclass
class Ramp(_VolumeModel):
    to: Optional[int] = None
    frm: Optional[int] = None

    def _volume(self, *args, **kwargs):
        raise ValueError("Ramp was called outside of a compound volume model")


@dataclass
class _RealRamp(_VolumeModel):
    _frm: int
    _to: int

    def _volume(self, start, end):
        percent = start / self.duration
        return int(self._frm + (self._to - self._frm) * percent)


@dataclass
class Compound(_VolumeModel):
    _left: InitVar[_VolumeModel]
    _right: InitVar[_VolumeModel]
    _realized: bool = field(init=False, default=False)

    def __post_init__(self, _left, _right):
        if isinstance(_left, Compound):
            l = _left._components
        else:
            l = (_left,)
        if isinstance(_right, Compound):
            r = _right._components
        else:
            r = (_right,)

        self._components = tuple(l + r)
        self.duration = _left.duration + _right.duration

    def _realize_ramps(self):
        cs = list(self._components)
        x = 0
        for i, c in enumerate(cs):
            if isinstance(c, Ramp):
                if i == 0:
                    if c.frm is not None:
                        frm = c.frm
                    else:
                        raise Exception(
                            "You must specify 'frm' on the first "
                            "Ramp in a chain of Volume Models"
                        )
                else:
                    if c.frm is not None:
                        # FIXME: not an error if frm == the preceding model's
                        # end tps
                        raise Exception(
                            "A ramp with 'frm' specified must be "
                            "the first volume model in a chain"
                        )
                    else:
                        frm = cs[i - 1][1](cs[i - 1][1].duration, 0)
                try:
                    to = cs[i + 1](0, 1)
                    if c.to is not None:
                        # FIXME: not actually an error if to == the tps of
                        # the next volume model...
                        raise Exception(
                            "A ramp with 'to' specified must be "
                            "the last volume model in a chain"
                        )
                except IndexError:
                    if c.to is None:
                        raise Exception(
                            "You must specify 'to' on the final "
                            "Ramp in a chain of Volume Models"
                        )
                    to = c.to
                c = _RealRamp(duration=c.duration, _frm=frm, _to=to)
            cs[i] = (x, c)
            x += c.duration

        self._components = cs
        self._realized = True

    def __call__(self, start, end):
        if not self._realized:
            self._realize_ramps()
        return super().__call__(start, end)

    def _volume(self, start, end):
        applicable = list(filter(lambda x: x[0] <= start, self._components))
        try:
            c = applicable[-1]
            return c[1](start - c[0], end - c[0])
        except StopIteration:  # pragma: no cover
            raise Exception("should never happen!")
