#!/bin/bash
# usage: batch.sh GROUP SH PT [PT...]   (first PT drives the stores)
cd /home/user/FAoutput/temp/tools
G=$1; SH=$2; shift 2
W=../work/stores; mkdir -p $W/pt/$G $W/sh/$G $W/png
for p in "$@"; do cp ../out/$G/$p $W/pt/$G/; done
args=(); for p in "$@"; do args+=($W/pt/$G/$p); done
python3 newsh/fitpt.py ../out/$G/$SH "${args[@]}" 2>&1 | grep " hp\|no wing"
python3 newsh/stores.py ../out/$G/$SH ${args[0]} $W/sh/$G/$SH > $W/sh/$G/${SH%.SH}.log 2>&1 || { echo "FAIL $SH"; tail -3 $W/sh/$G/${SH%.SH}.log; exit; }
python3 groundchk.py $W/sh/$G/$SH 2>&1 | tail -1
python3 shview.py $W/sh/$G/$SH - $W/png/${SH%.SH}.png --painter > /dev/null
echo "OK $SH $(stat -c%s $W/sh/$G/$SH)"
