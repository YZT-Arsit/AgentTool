# V12.2 baseline privacy dependency result

B0–B3 retain their exact historical values because their executable dependencies did not change: **1/14, 2/14, 11/14, and 13/14**. B4 and B5 require post-repair execution because they reach the changed canonical durable-state path. That execution was not permitted after the Linux Class-A serial gate failed, so their post-repair values are explicitly **NOT RUN**, not copied from the historical 13/14 and 14/14 results.

This matrix makes no new privacy claim and does not force B4/B5 equality.
