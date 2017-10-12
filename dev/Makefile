all: api plot clean

api: clean
	@python3 api.py

plot:
	@gnuplot plot.gnu

clean:
	@rm -rf *.log
