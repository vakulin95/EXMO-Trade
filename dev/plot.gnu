set terminal png font "Times-Roman,10"
set grid
set xtics auto
set ytics auto
set mxtics
set mytics
set style data linespoints
set style line 1 lc rgb '#dd181f' lt 1 lw 1 pt 1 ps 1   # --- red
#set key outside bottom right box

plot_file = "workfile.dat"

title1 = "price"

set output "out.png"
	set title ""
	set xlabel "time"
	set ylabel "price"
	plot plot_file title title1 ls 1
unset out
