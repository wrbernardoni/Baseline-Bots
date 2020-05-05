import random
from reconchess import *
from sortedcontainers import SortedList

class FourDeepInference(Player):
	def __init__(self):
		self.board = None
		self.color = None
		self.moveNum = 0
		self.nextMove = None
		self.expectedEnemy = None
		self.approxTime = 900
		self.interestingTile = None

	def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
		self.board = board
		self.color = color

	def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):
		if captured_my_piece:
			self.interestingTile = capture_square
			self.board.remove_piece_at(capture_square)

	def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> \
			Optional[Square]:
		self.moveNum = self.moveNum + 1
		if self.interestingTile:
			return self.interestingTile

		if self.expectedEnemy is not None:
			if self.board.piece_at(self.expectedEnemy.to_square) is None:
				return self.expectedEnemy.to_square

		self.nextMove = self.choose_move(move_actions, seconds_left)
		if self.nextMove is not None:
			return self.nextMove.to_square

		for square, piece in self.board.piece_map().items():
			if piece.color == self.color:
				sense_actions.remove(square)

		return random.choice(sense_actions)

	def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
		self.interestingTile = None
		for square, piece in sense_result:
			if self.board.piece_at(square) != piece:
				self.nextMove = None
				if self.board.piece_at(square) is None:
					if self.board.turn is self.color:
						self.board.push(chess.Move.null())
					for move in self.board.legal_moves:
						if move.to_square == square and self.board.piece_at(move.from_square) == piece:
							self.board.push(move)
							break

			if self.expectedEnemy is not None and piece is not None and self.board.piece_at(self.expectedEnemy.from_square) is not None:
				if self.expectedEnemy.to_square == square and self.board.piece_at(self.expectedEnemy.from_square).piece_type == piece.piece_type:
					self.board.push(self.expectedEnemy)

			if piece is None:
				self.board.remove_piece_at(square)
			else:
				self.board.set_piece_at(square, piece)

	def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
		self.approxTime = seconds_left
		self.response = None
		if self.nextMove is not None:
			mv = self.nextMove
			self.nextMove = None
			return mv

		e_king_square = self.board.king(not self.color)
		if e_king_square:
			attackers = self.board.attackers(self.color, e_king_square)
			for attack in attackers:
				m = chess.Move(attack, e_king_square)
				if m in move_actions:
					return m

		m_king_square = self.board.king(self.color)
		if m_king_square:
			if self.board.turn is not self.color:
				self.board.push(chess.Move.null())
			attackers = self.board.attackers(not self.color, m_king_square)
			if attackers:
				legalMoves = self.board.legal_moves
				for move in legalMoves:
					tempBoard = self.board.copy()
					tempBoard.push(move)
					attackers = tempBoard.attackers(not self.color, tempBoard.king(self.color))
					if (attackers is None or len(attackers) is 0) and move in move_actions:
						return move

		class MvSrc:
			def __init__(self, board, iM, nm, scr):
				self.brd = board
				self.initialMove = iM
				self.moveNum = nm
				self.score = scr
				self.response = None

		def eval_board(board) -> float:
			score = 0
			for square, piece in board.piece_map().items():
				mult = 1
				attackers = board.attackers(not piece.color, square)
				defenders = board.attackers(piece.color, square)
				val = 0
				if piece.color != self.color:
					mult = -1
				if piece.piece_type == chess.PAWN:
					val = 5
				elif piece.piece_type == chess.KNIGHT:
					val = 10
				elif piece.piece_type == chess.BISHOP:
					val = 10
				elif piece.piece_type == chess.ROOK:
					val = 10
				elif piece.piece_type == chess.QUEEN:
					val = 20
				elif piece.piece_type == chess.KING:
					val = 100
				if len(attackers) != 0 and len(defenders) == 0 and piece.color == self.color:
					val = val / 10
				if len(defenders) != 0 and piece.piece_type != chess.KING:
					val = val * 2

				score = score + mult * val
			return score

		deep = 5
		mS = []
		for i in range(deep):
			msN = None
			if (i%2) != 0:
				msN = SortedList(key=lambda x: (x.score))
			else:
				msN = SortedList(key=lambda x: (-1 * x.score))
			mS.append(msN)

		if self.board.turn is not self.color:
			self.board.push(chess.Move.null())

		im = MvSrc(self.board, None, 0, eval_board(self.board));
		mS[0].add(im)
		winningMove = SortedList(key=lambda x: x.score  / (x.moveNum if x.moveNum != 0 else 1));

		for i in range(deep):
			moveSearch = mS[i]

			while len(moveSearch) is not 0:
				im = moveSearch.pop(0);

				initialMove = im.initialMove;
				tempBoard = im.brd

				if tempBoard.turn == self.color:
					m_king_square = tempBoard.king(self.color)
					if m_king_square:
						attackers = tempBoard.attackers(not self.color, m_king_square)
						if attackers:
							continue

				if im.moveNum == (deep - 1):
					if initialMove in move_actions:
						winningMove.add(im)
					continue

				e_king_square = tempBoard.king(not self.color)
				if e_king_square:
					attackers = tempBoard.attackers(self.color, e_king_square)
					if attackers:
						if initialMove in move_actions:
							im.score = im.score + 100
							winningMove.add(im)
						continue
				
				legalMoves = tempBoard.legal_moves
				for move in legalMoves:
					mv = None
					if initialMove is None and tempBoard.turn == self.color:
						mv = MvSrc(tempBoard.copy(), move, im.moveNum + 1, 0)
					else:
						mv = MvSrc(tempBoard.copy(), initialMove, im.moveNum + 1, 0)

					if tempBoard.turn != self.color and im.response is None:
						mv.response = move
					elif im.response is not None:
						mv.response = im.response

					mv.brd.push(move)
					mv.score = eval_board(mv.brd)

					mS[mv.moveNum].add(mv);
					winningMove.add(mv);
					if len(mS[mv.moveNum]) > (1000 if ((mv.moveNum%2) != 0) else 100):
						mS[mv.moveNum].pop(0)

				while len(winningMove) > 1000:
					winningMove.pop(0)

		while len(winningMove) > 0:
			wm = winningMove.pop(-1)
			mv = wm.initialMove
			self.expectedEnemy = wm.response
			if mv in move_actions:
				return mv

		return random.choice(move_actions + [None])

	def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
						   captured_opponent_piece: bool, capture_square: Optional[Square]):
		if taken_move is not None:
			self.board.push(taken_move)
		if requested_move is not taken_move:
			self.interestingTile = requested_move.to_square

		print ("4_deep: End move ", self.moveNum, " -- approx ", self.approxTime, " seconds left")

	def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
						game_history: GameHistory):
		pass
