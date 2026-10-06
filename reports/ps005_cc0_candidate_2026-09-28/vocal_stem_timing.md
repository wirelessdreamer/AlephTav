# Psalm 5 vocal stem: measured timing reference

This report contains no lyrics or transcript. It was produced offline from the single authorized WAV; the source was opened read-only and was not altered.

Source: `D:\Psalms\Piano Psalms\Psalm 5 - Every Morning - Piano Stems\Psalm 5 - Every Morning - Piano (Vocals).wav`
SHA-256: `C9C517BA3EA3B256EAA44E42406B2664B5CDD5FA36E707CBE1A87A0418C3E84D`

Measured format: 264.680 seconds (4:24.680); 48,000 Hz; 2 channels; 16-bit signed PCM little-endian; 12,704,640 sample frames.
Sample peak: -2.95 dBFS. Whole-file stereo RMS: -23.50 dBFS.

## Interpretation and limits

These are energy measurements, not listening, transcription, phonetic alignment, or a trained singing-voice detector. No local ASR runtime or model was available in the scoped capability checks. Do not infer words, syllable counts, linguistic stress, note lengths, melodic repetitions, time signature, or tempo from this report. No such estimates are supplied. Waveform peaks are not syllables. Low energy can arise within a sung syllable; reverb, doubled singing, or separation bleed can join different lines.

Use these timestamps to locate sections and candidate pauses when fitting the project's separate line-slot meter brief. Do not relabel the regions below as lyric lines without listening/alignment. In particular, the continuous regions around 111-143, 155-191, and 214-236 seconds can contain multiple lines.

## Activity regions

20 ms windows at 10 ms hops; channel-mean energy avoids stereo cancellation. The reference gate is -40 dBFS frame RMS. Gaps up to 0.40 s are joined; resulting islands shorter than 0.20 s are omitted. End times include the final 20 ms analysis window. This joining can intentionally cross a short pause. A minimum-duration filter can omit short high-amplitude sounds. Boundaries are algorithmic at 10 ms resolution, not 10 ms phonetic accuracy.

The last two columns show sensitivity of each outer edge across -35, -40 and -45 dBFS, taking overlapping islands. Where an island splits, only fragments within 0.75 s of its outer boundary are considered for the matching outer edge. These are sensitivity ranges, not statistical confidence intervals.

| Region | Start s | End s | Duration s | Gap to next s | Peak frame RMS dBFS | Start sensitivity s | End sensitivity s |
|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 26.04 | 28.56 | 2.52 | 1.29 | -20.89 | 26.02-26.06 | 28.54-28.80 |
| 2 | 29.85 | 34.58 | 4.73 | 1.48 | -20.23 | 29.44-29.85 | 34.57-34.60 |
| 3 | 36.06 | 41.46 | 5.4 | 4.52 | -20.41 | 36.01-36.17 | 41.45-41.60 |
| 4 | 45.98 | 55.8 | 9.82 | 0.98 | -16.83 | 45.90-46.04 | 55.70-55.83 |
| 5 | 56.78 | 63.93 | 7.15 | 0.68 | -15.51 | 56.75-56.82 | 63.82-64.16 |
| 6 | 64.61 | 67.3 | 2.69 | 1.4 | -18.9 | 64.58-64.65 | 67.24-68.01 |
| 7 | 68.7 | 77.85 | 9.15 | 1.04 | -16.03 | 68.66-68.85 | 77.73-78.14 |
| 8 | 78.89 | 85.59 | 6.7 | 25.67 | -16.93 | 78.87-78.92 | 85.39-85.63 |
| 9 | 111.26 | 142.76 | 31.5 | 12.01 | -15.39 | 111.20-111.28 | 142.53-142.86 |
| 10 | 154.77 | 191.08 | 36.31 | 2.22 | -15.28 | 154.74-154.84 | 190.82-191.34 |
| 11 | 193.3 | 195.43 | 2.13 | 0.81 | -20.31 | 193.30-193.31 | 195.43-195.53 |
| 12 | 196.24 | 211.85 | 15.61 | 2.11 | -14.47 | 196.18-196.46 | 211.66-212.17 |
| 13 | 213.96 | 235.5 | 21.54 | 0.84 | -13.24 | 213.95-214.07 | 235.42-235.72 |
| 14 | 236.34 | 239.8 | 3.46 | 12.58 | -21.02 | 236.30-236.39 | 239.74-240.06 |
| 15 | 252.38 | 253.21 | 0.83 | 11.47 | -25.91 | 252.25-252.40 | 252.63-253.47 |

The final gap is to the file end. At a looser -45 dBFS threshold an additional short event appears at 249.67-250.00 s; the 252.38-253.21 s reference event is also brief. Both are unclassified sounds and should not automatically become lyric slots.

Long low-energy gaps in the -40 dBFS reference include 0.00-26.04 s, 41.46-45.98 s, 85.59-111.26 s, 142.76-154.77 s, 191.08-193.30 s, 211.85-213.96 s, and 239.80-252.38 s. The last includes the weaker event near 249.7 s. These indicate locations to check for instrumental passages or pauses, not proven musical section labels.

## Files

- `measurements.json`: format, hash, methods, and every reference region at gates from -25 to -50 dBFS.
- `frame_rms.csv`: 20 ms RMS every 10 ms across the full stem.
- `activity_regions.csv`: the table above in machine-readable form.
- `low_energy_intervals.csv`: all unbridged below-threshold spans at least 0.15 s long for -30, -35, -40 and -45 dBFS, for manual alignment support. These are not automatically breaths.
- `activity_envelope.png`: RMS envelope in five time strips, with threshold lines.
- `analyze_vocal.py`: reproducible offline analysis; requires NumPy and Pillow.

No reliable stress, syllabic onset, sustained-note, repetition, or tempo result was obtained. Obtaining those requires auditory validation and/or a suitable singing alignment/pitch method; the present measurements alone cannot settle them.


