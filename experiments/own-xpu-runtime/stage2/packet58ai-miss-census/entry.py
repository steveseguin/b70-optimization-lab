import sys
import screen
def main():
    if '--plan' not in sys.argv:
        import seal
        seal.verify()
    return screen.main(sys.argv[1:])
if __name__=='__main__':raise SystemExit(main())
