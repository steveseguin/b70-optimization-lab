10 | set_partitions | k=1 was rejected; guard should only reject k <= 0
11 | constrained_batches | batch flushed only when size AND count limits both hit; should be either
12 | intersperse | n==1 and n!=1 branch conditions swapped; fillers placed every item for n>1
13 | callback_iter | _aborted initialized to True so callback raised AbortThread immediately
14 | numeric_range | _get_by_index used impossible condition (i<0 and i>=len) so IndexError never raised
15 | mark_ends | last item yielded with is_last=False instead of True
17 | iter_except | loop was 'while False' so func was never called after first
18 | unzip | 'if head' inverted; returned () for non-empty and proceeded for empty
19 | all_unique | unhashable repeat returned True instead of False
20 | seekable | __bool__ returned False even when items remained; should return True
21 | split_before | maxsplit guard inverted ('!= 0' instead of '== 0'); yielded whole list normally
22 | sieve | guard 'n >= 2' yielded 2 for sieve(2); should be 'n > 2' (primes less than n)
23 | nth_combination | loop decremented r as 'r + 1' so it never terminated; should be 'r - 1'
24 | sliding_window | n==2 branch written as 'n != 2'; n=2 raised ValueError, n=1 returned pairwise
25 | split_at | 'maxsplit != 1' inverted; stopped after first separator instead of last
26 | combination_index | match condition inverted ('x != y' should be 'x == y'); indexes recorded skipped positions instead of matched ones
27 | bucket | __contains__ returned False even when item found; should return True
28 | unique_in_window | discard guard 'len(window) != n' should be '== n'; accessed empty deque
29 | powerset | range(len(s) - 1) should be range(len(s) + 1); only yielded subsets of size 0 and 1
30 | sample | guard 'k <= 0' rejected k=0; should be 'k < 0' so k=0 returns []
31 | nth_combination_with_replacement | total count used comb(n+r+1, r); should be comb(n+r-1, r) so invalid index raises IndexError
32 | one | 'too_long and ValueError(msg)' raised None when too_long was None; should be 'or' like the too_short line
33 | grouper | 'incomplete != strict' inverted; strict raised ValueError and ignore used _zip_equal; should be '=='
34 | polynomial_eval | 'if n != 0' inverted; returned 0 for non-empty and skipped type-preserving 0 for empty; should be 'n == 0'
35 | chunked | strict check 'len(chunk) == n' inverted; raised on full chunks, missed incomplete last chunk; should be '!='
36 | gray_product | direction flip condition used "and" instead of "or"; index ran past bounds
