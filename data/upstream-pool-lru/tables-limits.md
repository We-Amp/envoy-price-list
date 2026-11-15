| Arm | Rate | valid reps | p99 us per rep (x = invalid leg) | busiest worker, hop A / hop B, of a core (median) | client busiest thread | why invalid |
|---|---|---|---|---|---|---|
| mru | 8000 | 3/3 | 7814 / 1431 / 1822 | 0.41 / 0.86 | 0.26 | - |
| mru | 9600 | 3/3 | 2253 / 1879 / 1743 | 0.48 / 0.91 | 0.27 | - |
| mru | 11200 | 2/3 | 2515 / 11589 / 2461x | 0.54 / 0.93 | 0.28 | client pending total |
| mru | 12800 | 1/3 | 5950x / 6102x / 9863 | 0.60 / 1.00 | 0.29 | client pending total |
| mru | 14400 | 0/3 | 2786x / 5869x / 7968x | 0.66 / 1.00 | 0.30 | client pending total; client pool overflow; scheduler run time probe inconsistent: foreign -0.0286, siblings 0.0062 CPUs |
| mru | 16000 | 0/3 | 7052x / 3419x / 4874x | 0.72 / 1.00 | 0.31 | client pending total; client pool overflow; scheduler run time probe inconsistent: foreign -0.0399, siblings 0.0018 CPUs |
| mru | 17600 | 0/3 | 6862x / 3555x / 6150x | 0.77 / 1.00 | 0.31 | client pending total; client pool overflow; scheduler run time probe inconsistent: foreign -0.0126, siblings 0.0012 CPUs |
| mru | 19200 | 0/3 | 7938x / 3695x / 6634x | 0.82 / 1.00 | 0.33 | client pending total; client pool overflow |
| mru | 20800 | 0/3 | 4788x / 5331x / 12354x | 0.88 / 1.00 | 0.34 | client pending total; client pool overflow; scheduler run time probe inconsistent: foreign -0.0292, siblings 0.0007 CPUs |
| lru | 8000 | 3/3 | 1647 / 1480 / 2255 | 0.43 / 0.43 | 0.28 | - |
| lru | 9600 | 3/3 | 2045 / 2426 / 2438 | 0.50 / 0.50 | 0.27 | - |
| lru | 11200 | 3/3 | 2412 / 1882 / 1998 | 0.57 / 0.57 | 0.28 | - |
| lru | 12800 | 1/3 | 2595x / 3195x / 2191 | 0.64 / 0.65 | 0.29 | client pending total; client pool overflow |
| lru | 14400 | 0/3 | 2318x / 2609x / 3142x | 0.70 / 0.71 | 0.30 | client pending total; client pool overflow |
| lru | 16000 | 0/3 | 4599x / 3990x / 5269x | 0.77 / 0.77 | 0.30 | client pending total; client pool overflow |
| lru | 17600 | 0/3 | 6645x / 7744x / 4361x | 0.83 / 0.84 | 0.31 | client pending total; client pool overflow |
| lru | 19200 | 0/3 | 7126x / 11414x / 9992x | 0.89 / 0.89 | 0.32 | client pending total; client pool overflow |
| lru | 20800 | 0/3 | 21162x / 17748x / 6580x | 0.93 / 0.92 | 0.33 | client pending total; client pool overflow |
